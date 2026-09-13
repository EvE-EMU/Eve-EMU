"""User webhook notification rules — event detection + digest delivery."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemNotification
from app.models.member_audit import (
    WebhookNotificationDelivery,
    WebhookNotificationPending,
    WebhookNotificationRule,
)
from app.services.character_roster import resolve_owner_user_id, roster_character_ids

logger = logging.getLogger(__name__)
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; webhook-alerts)"

DELIVERY_MODES: dict[str, dict[str, Any]] = {
    "instant": {"label": "Instant", "seconds": 0},
    "hourly": {"label": "Hourly digest", "seconds": 3600},
    "4h": {"label": "Every 4 hours", "seconds": 14400},
    "8h": {"label": "Every 8 hours", "seconds": 28800},
    "daily": {"label": "Once per day", "seconds": 86400},
    "weekly": {"label": "Once per week", "seconds": 604800},
}

EVENT_CATALOG: list[dict[str, Any]] = [
    {
        "event_type": "skill_training_complete",
        "label": "Skill training complete",
        "description": "A queued skill finishes training.",
        "match_fields": ["skill_type_ids", "min_finished_level"],
    },
    {
        "event_type": "skill_queue_empty",
        "label": "No skills in training",
        "description": "Skill queue becomes empty.",
        "match_fields": [],
    },
    {
        "event_type": "skill_queue_low",
        "label": "Skill queue has open slots",
        "description": "Fewer than N skills queued (default 5).",
        "match_fields": ["max_queue_size"],
    },
    {
        "event_type": "contract_accepted",
        "label": "Contract accepted",
        "description": "Contract moves to in-progress / accepted.",
        "match_fields": ["contract_types", "title_contains"],
    },
    {
        "event_type": "contract_completed",
        "label": "Contract completed",
        "description": "Contract status becomes completed.",
        "match_fields": ["contract_types", "title_contains"],
    },
    {
        "event_type": "contract_expired",
        "label": "Contract expired",
        "description": "Contract status becomes expired.",
        "match_fields": ["contract_types"],
    },
    {
        "event_type": "contract_issued",
        "label": "New contract issued",
        "description": "A new contract appears on the character.",
        "match_fields": ["contract_types", "title_contains"],
    },
    {
        "event_type": "wallet_below",
        "label": "Wallet below threshold",
        "description": "Wallet balance drops under configured ISK amount.",
        "match_fields": ["wallet_threshold_isk"],
    },
    {
        "event_type": "wallet_above",
        "label": "Wallet above threshold",
        "description": "Wallet balance rises above configured ISK amount.",
        "match_fields": ["wallet_threshold_isk"],
    },
    {
        "event_type": "mail_subject_match",
        "label": "Mail subject match",
        "description": "Incoming mail subject matches patterns.",
        "match_fields": ["patterns", "regex"],
    },
    {
        "event_type": "sync_scope_error",
        "label": "Audit sync scope error",
        "description": "Character audit sync reports missing scopes or token errors.",
        "match_fields": ["scope_keys"],
    },
    {
        "event_type": "pi_extraction_complete",
        "label": "PI extraction complete",
        "description": "Extractor cycle completes or extractor head depletes (needs redeploy).",
        "match_fields": ["planet_ids"],
    },
    {
        "event_type": "pi_planet_idle",
        "label": "PI planet idle",
        "description": "Colony has no active extractors — player interaction needed.",
        "match_fields": ["planet_ids"],
    },
    {
        "event_type": "pi_extractor_expiring",
        "label": "PI extractor expiring soon",
        "description": "Extractor head expires within configured hours.",
        "match_fields": ["planet_ids", "hours_before"],
    },
    {
        "event_type": "pi_storage_attention",
        "label": "PI storage filling up",
        "description": "Planet storage crosses fill threshold (default 85%).",
        "match_fields": ["planet_ids", "storage_pct"],
    },
]


@dataclass
class DetectedEvent:
    event_key: str
    title: str
    body: str
    payload: dict[str, Any]


def _loads(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _queue_fingerprint(queue: list[dict]) -> set[tuple[int, str]]:
    out: set[tuple[int, str]] = set()
    for row in queue:
        if not isinstance(row, dict):
            continue
        sid = int(row.get("skill_type_id") or row.get("skill_id") or 0)
        if sid <= 0:
            continue
        out.add((sid, str(row.get("finish_date") or "")))
    return out


def _contract_map(contracts: list[dict]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for c in contracts:
        if not isinstance(c, dict):
            continue
        cid = int(c.get("contract_id") or 0)
        if cid > 0:
            out[cid] = c
    return out


def _matches_character(rule: WebhookNotificationRule, character_id: int, roster_ids: set[int]) -> bool:
    if rule.all_characters:
        return character_id in roster_ids
    target = int(rule.target_character_id or 0)
    return target > 0 and character_id == target


def _match_contract_filters(cfg: dict, contract: dict) -> bool:
    types = {str(t) for t in cfg.get("contract_types") or []}
    if types and str(contract.get("type") or "") not in types:
        return False
    needle = str(cfg.get("title_contains") or "").strip().lower()
    if needle and needle not in str(contract.get("title") or "").lower():
        return False
    return True


def detect_events(
    *,
    event_type: str,
    match_json: str,
    character_id: int,
    character_name: str,
    prev_snapshot: dict,
    new_snapshot: dict,
    scope_errors: dict[str, str] | None = None,
) -> list[DetectedEvent]:
    cfg = _loads(match_json)
    events: list[DetectedEvent] = []
    now = datetime.now(UTC)

    if event_type == "skill_training_complete":
        prev_q = _queue_fingerprint(prev_snapshot.get("skill_queue") or [])
        new_q = _queue_fingerprint(new_snapshot.get("skill_queue") or [])
        completed = prev_q - new_q
        allowed_skills = {int(x) for x in cfg.get("skill_type_ids") or []}
        min_level = int(cfg.get("min_finished_level") or 0)
        prev_rows = {
            (int(r.get("skill_type_id") or 0), str(r.get("finish_date") or "")): r
            for r in (prev_snapshot.get("skill_queue") or [])
            if isinstance(r, dict)
        }
        for sid, finish in completed:
            if allowed_skills and sid not in allowed_skills:
                continue
            row = prev_rows.get((sid, finish), {})
            level = int(row.get("finished_level") or 0)
            if min_level and level < min_level:
                continue
            finish_dt = _parse_ts(finish)
            if finish_dt and finish_dt > now:
                continue
            skill_name = str(row.get("skill_name") or f"Skill {sid}")
            events.append(
                DetectedEvent(
                    event_key=f"skill_done:{sid}:{finish}",
                    title=f"{character_name}: skill training complete",
                    body=f"{skill_name} reached level {level or '?'}",
                    payload={
                        "character_id": character_id,
                        "skill_type_id": sid,
                        "skill_name": skill_name,
                        "finished_level": level,
                        "finish_date": finish,
                    },
                )
            )

    elif event_type == "skill_queue_empty":
        prev_len = len(prev_snapshot.get("skill_queue") or [])
        new_len = len(new_snapshot.get("skill_queue") or [])
        if new_len == 0 and prev_len > 0:
            events.append(
                DetectedEvent(
                    event_key="skill_queue_empty",
                    title=f"{character_name}: skill queue empty",
                    body="No skills are currently training.",
                    payload={"character_id": character_id, "previous_queue_size": prev_len},
                )
            )

    elif event_type == "skill_queue_low":
        max_size = int(cfg.get("max_queue_size") or 5)
        new_len = len(new_snapshot.get("skill_queue") or [])
        prev_len = len(prev_snapshot.get("skill_queue") or [])
        if new_len < max_size and prev_len >= max_size:
            events.append(
                DetectedEvent(
                    event_key=f"skill_queue_low:{new_len}",
                    title=f"{character_name}: skill queue has open slots",
                    body=f"Only {new_len} skill(s) queued (threshold {max_size}).",
                    payload={"character_id": character_id, "queue_size": new_len, "threshold": max_size},
                )
            )

    elif event_type in {"contract_accepted", "contract_completed", "contract_expired", "contract_issued"}:
        prev_c = _contract_map(prev_snapshot.get("contracts") or [])
        new_c = _contract_map(new_snapshot.get("contracts") or [])
        if event_type == "contract_issued":
            for cid, contract in new_c.items():
                if cid in prev_c:
                    continue
                if not _match_contract_filters(cfg, contract):
                    continue
                events.append(
                    DetectedEvent(
                        event_key=f"contract_issued:{cid}",
                        title=f"{character_name}: new contract",
                        body=str(contract.get("title") or f"Contract {cid}"),
                        payload={"character_id": character_id, "contract": contract},
                    )
                )
        else:
            target_status = {
                "contract_accepted": {"in_progress", "finished_executor", "finished_issuer"},
                "contract_completed": {"completed"},
                "contract_expired": {"expired", "cancelled", "rejected"},
            }[event_type]
            for cid, contract in new_c.items():
                if not _match_contract_filters(cfg, contract):
                    continue
                prev_status = str(prev_c.get(cid, {}).get("status") or "")
                new_status = str(contract.get("status") or "")
                if new_status in target_status and prev_status != new_status:
                    events.append(
                        DetectedEvent(
                            event_key=f"{event_type}:{cid}:{new_status}",
                            title=f"{character_name}: contract {new_status.replace('_', ' ')}",
                            body=str(contract.get("title") or f"Contract {cid}"),
                            payload={
                                "character_id": character_id,
                                "contract_id": cid,
                                "status": new_status,
                                "contract": contract,
                            },
                        )
                    )

    elif event_type in {"wallet_below", "wallet_above"}:
        threshold = Decimal(str(cfg.get("wallet_threshold_isk") or 0))
        if threshold <= 0:
            return events
        prev_bal = Decimal(str(prev_snapshot.get("wallet_balance_isk") or 0))
        new_bal = Decimal(str(new_snapshot.get("wallet_balance_isk") or 0))
        if event_type == "wallet_below" and prev_bal >= threshold > new_bal:
            events.append(
                DetectedEvent(
                    event_key=f"wallet_below:{threshold}",
                    title=f"{character_name}: wallet below threshold",
                    body=f"Balance {new_bal:,.0f} ISK (threshold {threshold:,.0f})",
                    payload={
                        "character_id": character_id,
                        "balance_isk": str(new_bal),
                        "threshold_isk": str(threshold),
                    },
                )
            )
        elif event_type == "wallet_above" and prev_bal <= threshold < new_bal:
            events.append(
                DetectedEvent(
                    event_key=f"wallet_above:{threshold}",
                    title=f"{character_name}: wallet above threshold",
                    body=f"Balance {new_bal:,.0f} ISK (threshold {threshold:,.0f})",
                    payload={
                        "character_id": character_id,
                        "balance_isk": str(new_bal),
                        "threshold_isk": str(threshold),
                    },
                )
            )

    elif event_type == "mail_subject_match":
        patterns = [str(p) for p in cfg.get("patterns") or [] if str(p).strip()]
        if not patterns:
            return events
        use_regex = bool(cfg.get("regex"))
        prev_ids = {
            int(m.get("mail_id") or 0)
            for m in (prev_snapshot.get("mail") or [])
            if isinstance(m, dict)
        }
        for mail in new_snapshot.get("mail") or []:
            if not isinstance(mail, dict):
                continue
            mid = int(mail.get("mail_id") or 0)
            if mid in prev_ids:
                continue
            subject = str(mail.get("subject") or "")
            matched = False
            for pat in patterns:
                if use_regex:
                    try:
                        if re.search(pat, subject, re.I):
                            matched = True
                            break
                    except re.error:
                        continue
                elif pat.lower() in subject.lower():
                    matched = True
                    break
            if matched:
                events.append(
                    DetectedEvent(
                        event_key=f"mail:{mid}",
                        title=f"{character_name}: mail subject match",
                        body=subject[:200],
                        payload={"character_id": character_id, "mail_id": mid, "subject": subject},
                    )
                )

    elif event_type == "sync_scope_error" and scope_errors:
        keys = {str(k) for k in cfg.get("scope_keys") or []}
        for key, msg in scope_errors.items():
            if keys and key not in keys:
                continue
            events.append(
                DetectedEvent(
                    event_key=f"scope_error:{key}",
                    title=f"{character_name}: audit sync issue ({key})",
                    body=str(msg)[:300],
                    payload={"character_id": character_id, "scope_key": key, "message": msg},
                )
            )

    elif event_type.startswith("pi_"):
        from app.services.pi_sync import detect_pi_webhook_events

        for item in detect_pi_webhook_events(
            match_json=match_json,
            event_type=event_type,
            character_id=character_id,
            character_name=character_name,
            prev_snapshot=prev_snapshot,
            new_snapshot=new_snapshot,
        ):
            events.append(
                DetectedEvent(
                    event_key=item["event_key"],
                    title=item["title"],
                    body=item["body"],
                    payload=item.get("payload") or {},
                )
            )

    return events


def _create_in_app(recipient_id: int, event: DetectedEvent, rule: WebhookNotificationRule) -> SystemNotification:
    return SystemNotification(
        plugin="webhook_alerts",
        type=rule.event_type,
        title=event.title,
        body=event.body,
        payload_json=json.dumps(
            {"rule_id": rule.id, "rule_name": rule.name, **event.payload}, default=str
        ),
        recipient_character_id=recipient_id,
        read=False,
    )


async def _post_webhook(url: str, content: str) -> str:
    if not url.strip():
        return "skipped"
    payload = {"content": content[:1900]}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url.strip(), json=payload, headers={"User-Agent": _UA})
        return "ok" if resp.status_code < 400 else f"http_{resp.status_code}"
    except Exception as exc:
        logger.warning("Webhook notification delivery failed: %s", exc)
        return "error"


async def _deliver_instant(
    session: AsyncSession,
    rule: WebhookNotificationRule,
    character_id: int,
    character_name: str,
    event: DetectedEvent,
) -> None:
    content = f"**{event.title}**\n{event.body}\n_Rule: {rule.name}_"
    status = await _post_webhook(rule.webhook_url, content)
    if rule.notify_in_app:
        session.add(_create_in_app(character_id, event, rule))
    session.add(
        WebhookNotificationDelivery(
            rule_id=rule.id,
            character_id=character_id,
            delivery_mode="instant",
            event_count=1,
            webhook_status=status,
            detail=event.body[:500],
        )
    )


async def _enqueue_digest(
    session: AsyncSession,
    rule: WebhookNotificationRule,
    character_id: int,
    character_name: str,
    event: DetectedEvent,
) -> None:
    exists = await session.scalar(
        select(WebhookNotificationPending.id)
        .where(
            WebhookNotificationPending.rule_id == rule.id,
            WebhookNotificationPending.event_key == event.event_key,
            WebhookNotificationPending.character_id == character_id,
        )
        .limit(1)
    )
    if exists:
        return
    session.add(
        WebhookNotificationPending(
            rule_id=rule.id,
            character_id=character_id,
            character_name=character_name,
            event_key=event.event_key,
            title=event.title,
            body=event.body,
            payload_json=json.dumps(event.payload, default=str),
        )
    )
    if rule.notify_in_app:
        session.add(_create_in_app(character_id, event, rule))


async def evaluate_webhook_notifications(
    session: AsyncSession,
    character_id: int,
    *,
    character_name: str,
    prev_snapshot: dict,
    new_snapshot: dict,
    scope_errors: dict[str, str] | None = None,
) -> int:
    owner_id = await resolve_owner_user_id(session, character_id)
    if owner_id is None:
        return 0

    roster_ids = await roster_character_ids(session, character_id)
    rules = (
        await session.scalars(
            select(WebhookNotificationRule).where(
                WebhookNotificationRule.owner_user_id == int(owner_id),
                WebhookNotificationRule.enabled.is_(True),
            )
        )
    ).all()
    if not rules:
        return 0

    new_snapshot = dict(new_snapshot)
    new_snapshot.setdefault("wallet_balance_isk", new_snapshot.get("wallet_balance_isk", "0"))
    prev_snapshot = dict(prev_snapshot)

    fired = 0
    for rule in rules:
        if not _matches_character(rule, character_id, roster_ids):
            continue
        events = detect_events(
            event_type=rule.event_type,
            match_json=rule.match_json,
            character_id=character_id,
            character_name=character_name,
            prev_snapshot=prev_snapshot,
            new_snapshot=new_snapshot,
            scope_errors=scope_errors,
        )
        mode = rule.delivery_mode if rule.delivery_mode in DELIVERY_MODES else "instant"
        for event in events:
            if mode == "instant":
                await _deliver_instant(session, rule, character_id, character_name, event)
            else:
                await _enqueue_digest(session, rule, character_id, character_name, event)
            fired += 1
    return fired


async def flush_webhook_digests(session: AsyncSession) -> dict[str, int]:
    """Send buffered webhook events for rules whose digest interval has elapsed."""
    now = datetime.now(UTC)
    rules = (
        await session.scalars(
            select(WebhookNotificationRule).where(
                WebhookNotificationRule.enabled.is_(True),
                WebhookNotificationRule.delivery_mode != "instant",
            )
        )
    ).all()
    sent_rules = 0
    sent_events = 0
    for rule in rules:
        interval = DELIVERY_MODES.get(rule.delivery_mode, {}).get("seconds", 3600)
        if interval <= 0:
            continue
        last = rule.last_digest_at
        if last is not None and (now - last).total_seconds() < interval:
            continue
        pending = (
            await session.scalars(
                select(WebhookNotificationPending)
                .where(WebhookNotificationPending.rule_id == rule.id)
                .order_by(WebhookNotificationPending.created_at.asc())
                .limit(50)
            )
        ).all()
        if not pending:
            rule.last_digest_at = now
            continue
        lines = [f"**{rule.name}** — {len(pending)} event(s)", ""]
        for row in pending:
            lines.append(f"• **{row.title}** — {row.body[:120]}")
        content = "\n".join(lines)
        status = await _post_webhook(rule.webhook_url, content)
        for row in pending:
            await session.delete(row)
        session.add(
            WebhookNotificationDelivery(
                rule_id=rule.id,
                character_id=int(pending[0].character_id),
                delivery_mode=rule.delivery_mode,
                event_count=len(pending),
                webhook_status=status,
                detail=content[:500],
            )
        )
        rule.last_digest_at = now
        sent_rules += 1
        sent_events += len(pending)
    return {"rules_flushed": sent_rules, "events_sent": sent_events}
