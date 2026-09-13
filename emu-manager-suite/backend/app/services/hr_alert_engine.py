"""HR audit alert rules — evaluate on sync, webhook + in-app flags."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member_audit import (
    AuditSecurityFlag,
    CharacterInteractionAggregate,
    CharacterWalletJournal,
    HrAuditAlertEvent,
    HrAuditAlertRule,
)
from app.models.tools import AuditProfile, HrBlacklistEntry
from app.services.audit_snapshot import load_snapshot
from app.services.isk_format import fmt_isk_full

logger = logging.getLogger(__name__)
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; hr-alerts)"


def _loads(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


async def _blacklist_ids(session: AsyncSession) -> set[int]:
    rows = (
        await session.scalars(
            select(HrBlacklistEntry).where(
                HrBlacklistEntry.active.is_(True),
                HrBlacklistEntry.character_id.isnot(None),
            )
        )
    ).all()
    return {int(r.character_id) for r in rows if r.character_id}


async def _cooldown_active(
    session: AsyncSession,
    *,
    rule_id: int | None,
    character_id: int,
    flag_key: str,
    cooldown_hours: int,
) -> bool:
    if cooldown_hours <= 0:
        return False
    since = datetime.now(UTC) - timedelta(hours=cooldown_hours)
    row = await session.scalar(
        select(HrAuditAlertEvent)
        .where(
            HrAuditAlertEvent.rule_id == rule_id,
            HrAuditAlertEvent.character_id == character_id,
            HrAuditAlertEvent.flag_key == flag_key,
            HrAuditAlertEvent.created_at >= since,
        )
        .order_by(HrAuditAlertEvent.created_at.desc())
        .limit(1)
    )
    return row is not None


async def _fire_alert(
    session: AsyncSession,
    *,
    rule: HrAuditAlertRule | None,
    character_id: int,
    character_name: str,
    flag_key: str,
    severity: str,
    detail: str,
    open_flag_keys: set[str] | None = None,
    cooldown_keys: set[tuple[int | None, int, str]] | None = None,
) -> bool:
    rule_id = rule.id if rule else None
    cooldown = int(rule.cooldown_hours if rule else 24)
    cd_key = (rule_id, character_id, flag_key)
    if cooldown_keys is not None:
        if cooldown > 0 and cd_key in cooldown_keys:
            return False
    elif await _cooldown_active(
        session,
        rule_id=rule_id,
        character_id=character_id,
        flag_key=flag_key,
        cooldown_hours=cooldown,
    ):
        return False

    notify_in_app = rule.notify_in_app if rule else True
    if notify_in_app:
        if open_flag_keys is not None:
            if flag_key not in open_flag_keys:
                session.add(
                    AuditSecurityFlag(
                        character_id=character_id,
                        character_name=character_name,
                        flag_key=flag_key,
                        severity=severity,
                        detail=detail,
                    )
                )
                open_flag_keys.add(flag_key)
        else:
            exists = await session.scalar(
                select(AuditSecurityFlag).where(
                    AuditSecurityFlag.character_id == character_id,
                    AuditSecurityFlag.flag_key == flag_key,
                    AuditSecurityFlag.resolved.is_(False),
                )
            )
            if not exists:
                session.add(
                    AuditSecurityFlag(
                        character_id=character_id,
                        character_name=character_name,
                        flag_key=flag_key,
                        severity=severity,
                        detail=detail,
                    )
                )

    webhook_status = "skipped"
    webhook_url = (rule.webhook_url if rule else "") or ""
    if webhook_url.strip():
        payload = {
            "content": (
                f"**[{severity.upper()}] {character_name}** (`{character_id}`)\n"
                f"{detail}\n"
                f"`{flag_key}`"
            )[:1900],
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(webhook_url.strip(), json=payload, headers={"User-Agent": _UA})
            webhook_status = "ok" if resp.status_code < 400 else f"http_{resp.status_code}"
        except Exception as exc:
            webhook_status = "error"
            logger.warning("HR alert webhook failed: %s", exc)

    session.add(
        HrAuditAlertEvent(
            rule_id=rule_id,
            character_id=character_id,
            character_name=character_name,
            flag_key=flag_key,
            severity=severity,
            detail=detail,
            webhook_status=webhook_status,
        )
    )
    if cooldown_keys is not None and cooldown > 0:
        cooldown_keys.add(cd_key)
    return True


async def evaluate_hr_audit_rules(
    session: AsyncSession,
    character_id: int,
    *,
    prev_wallet: Decimal | None = None,
) -> int:
    profile = await session.scalar(
        select(AuditProfile).where(AuditProfile.character_id == character_id)
    )
    char_name = profile.character_name if profile else f"Character {character_id}"
    snapshot = load_snapshot(profile)
    rules = (
        await session.scalars(
            select(HrAuditAlertRule).where(HrAuditAlertRule.enabled.is_(True))
        )
    ).all()
    fired = 0
    blacklist = await _blacklist_ids(session)

    open_flag_keys = set(
        await session.scalars(
            select(AuditSecurityFlag.flag_key).where(
                AuditSecurityFlag.character_id == character_id,
                AuditSecurityFlag.resolved.is_(False),
            )
        )
    )
    max_cooldown = max((int(r.cooldown_hours) for r in rules), default=24)
    since = datetime.now(UTC) - timedelta(hours=max(1, max_cooldown))
    cooldown_keys = {
        (int(e.rule_id) if e.rule_id is not None else None, int(e.character_id), str(e.flag_key))
        for e in (
            await session.scalars(
                select(HrAuditAlertEvent).where(
                    HrAuditAlertEvent.character_id == character_id,
                    HrAuditAlertEvent.created_at >= since,
                )
            )
        ).all()
    }
    recent_journals = (
        await session.scalars(
            select(CharacterWalletJournal)
            .where(CharacterWalletJournal.character_id == character_id)
            .order_by(CharacterWalletJournal.recorded_at.desc())
            .limit(120)
        )
    ).all()

    for rule in rules:
        cfg = _loads(rule.match_json)
        rtype = rule.rule_type

        if rtype == "mail_subject":
            patterns = [str(p) for p in cfg.get("patterns") or [] if str(p).strip()]
            if not patterns:
                continue
            use_regex = bool(cfg.get("regex"))
            for mail in snapshot.get("mail") or []:
                if not isinstance(mail, dict):
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
                    key = f"{rule.rule_key}:{mail.get('mail_id') or subject[:32]}"
                    if await _fire_alert(
                        session,
                        rule=rule,
                        character_id=character_id,
                        character_name=char_name,
                        flag_key=key,
                        severity=rule.severity,
                        detail=f"Mail subject match ({rule.name}): {subject[:200]}",
                        open_flag_keys=open_flag_keys,
                        cooldown_keys=cooldown_keys,
                    ):
                        fired += 1

        elif rtype == "wallet_ref_type":
            ref_types = {str(t) for t in cfg.get("ref_types") or []}
            if not ref_types:
                continue
            journal_limit = int(cfg.get("journal_limit") or 80)
            for entry in recent_journals[:journal_limit]:
                if entry.ref_type not in ref_types:
                    continue
                party = int(entry.second_party_id or entry.first_party_id or 0)
                key = f"{rule.rule_key}:{entry.journal_id}"
                if await _fire_alert(
                    session,
                    rule=rule,
                    character_id=character_id,
                    character_name=char_name,
                    flag_key=key,
                    severity=rule.severity,
                    detail=(
                        f"Wallet {entry.ref_type} — {fmt_isk_full(entry.amount)}"
                        + (f" with {party}" if party else "")
                        + (f" — {entry.reason}" if entry.reason else "")
                    )[:500],
                    open_flag_keys=open_flag_keys,
                    cooldown_keys=cooldown_keys,
                ):
                    fired += 1

        elif rtype == "blacklist_contact":
            channels = cfg.get("channels") or [
                "wallet",
                "mail_received",
                "mail_sent",
                "combat_kill",
                "combat_loss",
                "contract",
            ]
            if blacklist:
                aggs = (
                    await session.scalars(
                        select(CharacterInteractionAggregate).where(
                            CharacterInteractionAggregate.character_id == character_id,
                            CharacterInteractionAggregate.counterparty_id.in_(blacklist),
                        )
                    )
                ).all()
            else:
                aggs = []
            for agg in aggs:
                if channels and agg.channel not in channels:
                    continue
                key = f"{rule.rule_key}:{agg.counterparty_id}:{agg.channel}"
                if await _fire_alert(
                    session,
                    rule=rule,
                    character_id=character_id,
                    character_name=char_name,
                    flag_key=key,
                    severity=rule.severity,
                    detail=(
                        f"Contact with blacklisted {agg.counterparty_name} ({agg.counterparty_id}) "
                        f"via {agg.channel} ×{agg.event_count}"
                    ),
                    open_flag_keys=open_flag_keys,
                    cooldown_keys=cooldown_keys,
                ):
                    fired += 1

            if "wallet" in channels or not channels:
                for entry in recent_journals[:50]:
                    party = int(entry.second_party_id or entry.first_party_id or 0)
                    if party in blacklist:
                        key = f"{rule.rule_key}:wallet:{party}"
                        if await _fire_alert(
                            session,
                            rule=rule,
                            character_id=character_id,
                            character_name=char_name,
                            flag_key=key,
                            severity=rule.severity,
                            detail=f"Wallet journal references blacklisted entity {party}",
                            open_flag_keys=open_flag_keys,
                            cooldown_keys=cooldown_keys,
                        ):
                            fired += 1

        elif rtype == "wallet_drop":
            threshold = float(cfg.get("threshold") or 0.5)
            if profile and prev_wallet is not None and prev_wallet > 0:
                drop = prev_wallet - profile.wallet_balance_isk
                if drop > prev_wallet * Decimal(str(threshold)):
                    key = rule.rule_key
                    if await _fire_alert(
                        session,
                        rule=rule,
                        character_id=character_id,
                        character_name=char_name,
                        flag_key=key,
                        severity=rule.severity,
                        detail=f"Wallet dropped {fmt_isk_full(drop)} since last snapshot",
                        open_flag_keys=open_flag_keys,
                        cooldown_keys=cooldown_keys,
                    ):
                        fired += 1

        elif rtype == "interaction_threshold":
            min_count = int(cfg.get("min_count") or 5)
            counterparty_id = int(cfg.get("counterparty_id") or 0)
            if counterparty_id <= 0:
                continue
            aggs = await session.scalars(
                select(CharacterInteractionAggregate).where(
                    CharacterInteractionAggregate.character_id == character_id,
                    CharacterInteractionAggregate.counterparty_id == counterparty_id,
                )
            )
            total = sum(int(a.event_count) for a in aggs.all())
            if total >= min_count:
                key = f"{rule.rule_key}:{counterparty_id}"
                if await _fire_alert(
                    session,
                    rule=rule,
                    character_id=character_id,
                    character_name=char_name,
                    flag_key=key,
                    severity=rule.severity,
                    detail=f"{total} interactions with entity {counterparty_id} (threshold {min_count})",
                    open_flag_keys=open_flag_keys,
                    cooldown_keys=cooldown_keys,
                ):
                    fired += 1

    return fired


async def seed_default_hr_rules(session: AsyncSession) -> None:
    """Idempotent default rules mirroring legacy security checks."""
    defaults = [
        HrAuditAlertRule(
            rule_key="blacklist_wallet_contact",
            name="Blacklisted wallet contact",
            description="Wallet journal references a blacklisted character ID.",
            rule_type="blacklist_contact",
            severity="critical",
            match_json=json.dumps({"channels": ["wallet"]}),
            notify_in_app=True,
            cooldown_hours=24,
        ),
        HrAuditAlertRule(
            rule_key="wallet_drop",
            name="Large wallet drop",
            description="Wallet balance fell more than 50% since last sync.",
            rule_type="wallet_drop",
            severity="warn",
            match_json=json.dumps({"threshold": 0.5}),
            notify_in_app=True,
            cooldown_hours=12,
        ),
        HrAuditAlertRule(
            rule_key="mail_subject_watch",
            name="Suspicious mail subject",
            description="Mail subject matches configured patterns (edit match_json patterns list).",
            rule_type="mail_subject",
            severity="warn",
            match_json=json.dumps({"patterns": ["recruit", "spy", "awox"], "regex": False}),
            enabled=False,
            notify_in_app=True,
            cooldown_hours=24,
        ),
    ]
    for row in defaults:
        exists = await session.scalar(
            select(HrAuditAlertRule).where(HrAuditAlertRule.rule_key == row.rule_key)
        )
        if not exists:
            session.add(row)
