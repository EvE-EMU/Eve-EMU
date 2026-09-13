"""Combined roster overview — aggregate all linked alts in one payload."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.member_audit import AuditSecurityFlag, CharacterAsset, CharacterWalletJournal
from app.models.tools import AuditProfile
from app.services.audit_snapshot import load_snapshot
from app.services.cache_ttl import cache_get, cache_set
from app.services.character_roster import load_roster, resolve_owner_user_id
from app.services.eve_time import format_eve_time
from app.services.roster_interactions import build_roster_interaction_summary


def _dec(value: Decimal | str | int | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _location_label(profile: AuditProfile | None) -> str | None:
    if not profile:
        return None
    snap = load_snapshot(profile)
    loc = snap.get("location") if isinstance(snap.get("location"), dict) else {}
    return (
        loc.get("location_name")
        or loc.get("system_name")
        or (str(loc.get("solar_system_id")) if loc.get("solar_system_id") else None)
    )


async def build_roster_overview(session: AsyncSession, viewer_character_id: int) -> dict:
    owner_id = await resolve_owner_user_id(session, viewer_character_id)
    cache_key = f"roster_overview:{owner_id or viewer_character_id}"
    if settings.roster_overview_cache_seconds > 0:
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

    roster = await load_roster(session, viewer_character_id)
    if not roster:
        return {
            "character_count": 0,
            "totals": {
                "wallet_balance_isk": "0",
                "assets_value_isk": "0",
                "skill_points": 0,
                "asset_item_count": 0,
                "open_flags": 0,
            },
            "characters": [],
            "combined_wallet_journal": [],
            "combined_flags": [],
            "interaction_summary": {
                "counterparty_count": 0,
                "interaction_events": 0,
                "top_counterparties": [],
            },
        }

    ids = [int(r.character_id) for r in roster]
    roster_map = {int(r.character_id): r for r in roster}

    profiles = (
        await session.scalars(select(AuditProfile).where(AuditProfile.character_id.in_(ids)))
    ).all()
    profile_map = {int(p.character_id): p for p in profiles}

    asset_count_rows = (
        await session.execute(
            select(CharacterAsset.character_id, func.count())
            .where(CharacterAsset.character_id.in_(ids))
            .group_by(CharacterAsset.character_id)
        )
    ).all()
    asset_counts = {int(cid): int(cnt) for cid, cnt in asset_count_rows}

    flag_rows = (
        await session.scalars(
            select(AuditSecurityFlag)
            .where(
                AuditSecurityFlag.character_id.in_(ids),
                AuditSecurityFlag.resolved.is_(False),
            )
            .order_by(AuditSecurityFlag.created_at.desc())
            .limit(200)
        )
    ).all()

    flags_by_char: dict[int, list[AuditSecurityFlag]] = defaultdict(list)
    for f in flag_rows:
        flags_by_char[int(f.character_id)].append(f)

    journal_rows = (
        await session.scalars(
            select(CharacterWalletJournal)
            .where(CharacterWalletJournal.character_id.in_(ids))
            .order_by(CharacterWalletJournal.recorded_at.desc())
            .limit(400)
        )
    ).all()

    total_wallet = Decimal("0")
    total_assets = Decimal("0")
    total_sp = 0
    total_items = 0

    characters: list[dict] = []
    for r in roster:
        cid = int(r.character_id)
        profile = profile_map.get(cid)
        wallet = _dec(profile.wallet_balance_isk if profile else 0)
        assets_val = _dec(profile.assets_value_isk if profile else 0)
        sp = int(profile.skill_points or 0) if profile else 0
        items = asset_counts.get(cid, 0)
        char_flags = flags_by_char.get(cid, [])

        total_wallet += wallet
        total_assets += assets_val
        total_sp += sp
        total_items += items

        last_sync = profile.last_sync_at if profile else None
        characters.append(
            {
                "character_id": cid,
                "character_name": r.character_name,
                "is_main": r.is_main,
                "token_valid": r.token_valid,
                "corporation_name": profile.corporation_name if profile else "",
                "wallet_balance_isk": str(wallet),
                "assets_value_isk": str(assets_val),
                "skill_points": sp,
                "asset_item_count": items,
                "current_location": _location_label(profile),
                "last_sync_at": last_sync.isoformat() if last_sync else None,
                "last_sync_eve": format_eve_time(last_sync),
                "open_flags": len(char_flags),
            }
        )

    name_by_id = {c["character_id"]: c["character_name"] for c in characters}

    payload = {
        "character_count": len(characters),
        "totals": {
            "wallet_balance_isk": str(total_wallet),
            "assets_value_isk": str(total_assets),
            "skill_points": total_sp,
            "asset_item_count": total_items,
            "open_flags": len(flag_rows),
        },
        "characters": characters,
        "combined_wallet_journal": [
            {
                "character_id": int(j.character_id),
                "character_name": name_by_id.get(int(j.character_id), f"Char {j.character_id}"),
                "ref_type": j.ref_type,
                "amount": str(j.amount),
                "balance": str(j.balance),
                "reason": j.reason,
                "recorded_at": j.recorded_at.isoformat(),
            }
            for j in journal_rows
        ],
        "combined_flags": [
            {
                "character_id": int(f.character_id),
                "character_name": name_by_id.get(int(f.character_id), f.character_name),
                "flag_key": f.flag_key,
                "severity": f.severity,
                "detail": f.detail,
            }
            for f in flag_rows
        ],
        "interaction_summary": await build_roster_interaction_summary(session, viewer_character_id),
    }
    if settings.roster_overview_cache_seconds > 0:
        await cache_set(cache_key, payload, ttl_seconds=settings.roster_overview_cache_seconds)
    return payload
