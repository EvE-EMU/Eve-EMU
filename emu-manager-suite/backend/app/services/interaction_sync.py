"""Rebuild per-character interaction aggregates from wallet DB + audit snapshot."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.member_audit import CharacterInteractionAggregate, CharacterWalletJournal
from app.models.tools import AuditProfile
from app.services.audit_snapshot import load_snapshot
from app.services.character_roster import resolve_owner_user_id
from app.services.entity_classify import classify_entity_id
from app.services.esi import resolve_universe_names

logger = logging.getLogger(__name__)

AggKey = tuple[int, str]  # (counterparty_id, channel)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _bump(
    bucket: dict[AggKey, dict],
    *,
    counterparty_id: int,
    channel: str,
    when: datetime | None,
    detail: str = "",
    amount: Decimal | None = None,
) -> None:
    if counterparty_id <= 0:
        return
    key = (counterparty_id, channel)
    row = bucket.get(key)
    if not row:
        bucket[key] = {
            "event_count": 1,
            "first_seen_at": when,
            "last_seen_at": when,
            "last_detail": detail[:512],
            "total_amount_isk": amount or Decimal("0"),
        }
        return
    row["event_count"] += 1
    if when and (row["first_seen_at"] is None or when < row["first_seen_at"]):
        row["first_seen_at"] = when
    if when and (row["last_seen_at"] is None or when > row["last_seen_at"]):
        row["last_seen_at"] = when
        row["last_detail"] = detail[:512]
    if amount is not None:
        row["total_amount_isk"] = row.get("total_amount_isk", Decimal("0")) + amount


async def sync_character_interactions(session: AsyncSession, character_id: int) -> int:
    owner_user_id = await resolve_owner_user_id(session, character_id)
    if owner_user_id is None:
        return 0

    profile = await session.scalar(
        select(AuditProfile).where(AuditProfile.character_id == character_id)
    )
    snapshot = load_snapshot(profile)
    bucket: dict[AggKey, dict] = {}

    cutoff = datetime.now(UTC) - timedelta(days=max(1, settings.interaction_journal_days))
    journal_limit = max(500, settings.interaction_journal_max_rows)
    journals = (
        await session.scalars(
            select(CharacterWalletJournal)
            .where(
                CharacterWalletJournal.character_id == character_id,
                CharacterWalletJournal.recorded_at >= cutoff,
            )
            .order_by(CharacterWalletJournal.recorded_at.desc())
            .limit(journal_limit)
        )
    ).all()
    for entry in journals:
        party = int(entry.second_party_id or entry.first_party_id or 0)
        if party <= 0:
            continue
        _bump(
            bucket,
            counterparty_id=party,
            channel="wallet",
            when=entry.recorded_at,
            detail=f"{entry.ref_type}: {entry.reason}"[:512],
            amount=Decimal(str(entry.amount or 0)),
        )

    for mail in snapshot.get("mail") or []:
        if not isinstance(mail, dict):
            continue
        when = _parse_ts(mail.get("timestamp"))
        subject = str(mail.get("subject") or "")
        from_id = int(mail.get("from_id") or 0)
        if from_id > 0 and from_id != character_id:
            _bump(
                bucket,
                counterparty_id=from_id,
                channel="mail_received",
                when=when,
                detail=subject[:512],
            )
        for recip in mail.get("recipient_ids") or []:
            if not isinstance(recip, dict):
                continue
            rid = int(recip.get("recipient_id") or 0)
            if rid > 0 and rid != character_id:
                _bump(
                    bucket,
                    counterparty_id=rid,
                    channel="mail_sent",
                    when=when,
                    detail=subject[:512],
                )

    for event in snapshot.get("combat_log") or []:
        if not isinstance(event, dict):
            continue
        when = _parse_ts(event.get("killed_at"))
        outcome = event.get("outcome")
        ship = str(event.get("ship_type_name") or "killmail")
        km_id = event.get("killmail_id")
        km_detail = f"{ship}" + (f" · KM {km_id}" if km_id else "")
        attackers = [int(a or 0) for a in (event.get("attacker_character_ids") or []) if int(a or 0) > 0]

        if outcome == "kill":
            vid = int(event.get("victim_character_id") or 0)
            if vid > 0:
                _bump(
                    bucket,
                    counterparty_id=vid,
                    channel="combat_kill",
                    when=when,
                    detail=km_detail[:512],
                )
            # Co-attackers on the same killmail = flew in fleet together (high alt signal).
            for aid in attackers:
                if aid != character_id:
                    _bump(
                        bucket,
                        counterparty_id=aid,
                        channel="combat_fleet",
                        when=when,
                        detail=f"Fleet co-attacker · {km_detail}"[:512],
                    )
        elif outcome == "loss":
            for aid in attackers:
                if aid != character_id:
                    _bump(
                        bucket,
                        counterparty_id=aid,
                        channel="combat_loss",
                        when=when,
                        detail=km_detail[:512],
                    )

    for contract in snapshot.get("contracts") or []:
        if not isinstance(contract, dict):
            continue
        when = _parse_ts(contract.get("start_date"))
        title = str(contract.get("title") or contract.get("type") or "contract")
        for field in ("issuer_id", "assignee_id", "acceptor_id"):
            pid = int(contract.get(field) or 0)
            if pid > 0 and pid != character_id:
                _bump(
                    bucket,
                    counterparty_id=pid,
                    channel="contract",
                    when=when,
                    detail=title[:512],
                )

    for contact in snapshot.get("contacts") or []:
        if not isinstance(contact, dict):
            continue
        cid = int(contact.get("contact_id") or 0)
        if cid <= 0 or cid == character_id:
            continue
        standing = contact.get("standing")
        label = str(contact.get("label") or contact.get("contact_name") or "contact")
        flags = []
        if contact.get("is_blocked"):
            flags.append("blocked")
        if contact.get("is_watched"):
            flags.append("watched")
        detail = label
        if standing is not None:
            detail = f"standing {float(standing):+.1f} · {label}"
        if flags:
            detail = f"{detail} · {','.join(flags)}"
        _bump(
            bucket,
            counterparty_id=cid,
            channel="contact",
            when=None,
            detail=detail[:512],
        )


    await session.execute(
        delete(CharacterInteractionAggregate).where(
            CharacterInteractionAggregate.character_id == character_id
        )
    )

    if not bucket:
        return 0

    name_ids = list({cid for cid, _ in bucket})
    names = await resolve_universe_names(name_ids)
    now = datetime.now(UTC)

    mappings = [
        {
            "owner_user_id": int(owner_user_id),
            "character_id": character_id,
            "counterparty_id": counterparty_id,
            "counterparty_kind": classify_entity_id(counterparty_id),
            "counterparty_name": names.get(counterparty_id, f"Entity {counterparty_id}"),
            "channel": channel,
            "event_count": int(data["event_count"]),
            "first_seen_at": data.get("first_seen_at"),
            "last_seen_at": data.get("last_seen_at"),
            "last_detail": str(data.get("last_detail") or ""),
            "total_amount_isk": Decimal(str(data.get("total_amount_isk") or 0)),
            "updated_at": now,
        }
        for (counterparty_id, channel), data in bucket.items()
    ]
    await session.execute(insert(CharacterInteractionAggregate), mappings)
    return len(mappings)
