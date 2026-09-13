"""Killboard leaderboard — zKillboard stats + in-game combat log from audit snapshots."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.tools import AuditProfile, KillboardLeaderboard, LinkedCharacter, SdeTypeIndex, SsoUser
from app.services.audit_snapshot import load_snapshot
from app.services.esi import resolve_universe_names
from app.services.zkill import (
    fetch_character_recent_kills,
    fetch_character_stats,
    fetch_scope_recent_kills,
    fetch_scope_stats,
)

logger = logging.getLogger(__name__)

_STALE_HOURS = 6


def _period_month_keys(period_days: int) -> set[str]:
    """YYYYMM keys covering the last `period_days` (approximate calendar months)."""
    now = datetime.now(UTC)
    keys: set[str] = set()
    for offset in range(max(1, (period_days // 28) + 1)):
        dt = now - timedelta(days=offset * 28)
        keys.add(dt.strftime("%Y%m"))
    return keys


def _stats_for_period(raw: dict[str, Any], period_days: int) -> dict[str, int | float]:
    """Extract kills/losses/isk for a rolling period from zKill stats payload."""
    months = raw.get("months")
    if isinstance(months, dict) and period_days < 365:
        keys = _period_month_keys(period_days)
        kills = losses = 0
        isk_destroyed = isk_lost = 0.0
        matched = False
        for key, bucket in months.items():
            if str(key) not in keys or not isinstance(bucket, dict):
                continue
            matched = True
            kills += int(bucket.get("shipsDestroyed") or 0)
            losses += int(bucket.get("shipsLost") or 0)
            isk_destroyed += float(bucket.get("iskDestroyed") or 0)
            isk_lost += float(bucket.get("iskLost") or 0)
        if matched:
            return {
                "kills": kills,
                "losses": losses,
                "isk_destroyed": isk_destroyed,
                "isk_lost": isk_lost,
            }
    return {
        "kills": int(raw.get("shipsDestroyed") or 0),
        "losses": int(raw.get("shipsLost") or 0),
        "isk_destroyed": float(raw.get("iskDestroyed") or 0),
        "isk_lost": float(raw.get("iskLost") or 0),
    }


def _top_characters_from_scope_stats(raw: dict[str, Any]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for block in raw.get("topLists") or []:
        if not isinstance(block, dict) or block.get("type") != "character":
            continue
        for row in block.get("values") or []:
            if not isinstance(row, dict):
                continue
            cid = int(row.get("characterID") or row.get("id") or 0)
            name = str(row.get("characterName") or row.get("name") or f"Character {cid}")
            if cid > 0:
                out.append((cid, name))
    return out


async def _scope_member_ids(session: AsyncSession, scope: str, scope_id: int) -> dict[int, str]:
    """Character IDs in scope with display names (SSO users + linked alts)."""
    names: dict[int, str] = {}
    if scope == "alliance":
        users = (
            await session.scalars(select(SsoUser).where(SsoUser.alliance_id == scope_id))
        ).all()
    else:
        users = (
            await session.scalars(select(SsoUser).where(SsoUser.corporation_id == scope_id))
        ).all()
    for user in users:
        names[int(user.character_id)] = user.character_name

    if users:
        owner_ids = [int(u.id) for u in users]
        linked = (
            await session.scalars(select(LinkedCharacter).where(LinkedCharacter.owner_user_id.in_(owner_ids)))
        ).all()
        for row in linked:
            names[int(row.character_id)] = row.character_name
    return names


def _combat_totals(snapshot: dict, *, period_days: int) -> dict[str, int]:
    cutoff = datetime.now(UTC) - timedelta(days=max(1, period_days))
    events = snapshot.get("combat_log") if isinstance(snapshot.get("combat_log"), list) else []
    kills = losses = 0
    for ev in events:
        if not isinstance(ev, dict):
            continue
        ts = ev.get("killed_at")
        if ts:
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                if dt < cutoff:
                    continue
            except (TypeError, ValueError):
                pass
        outcome = str(ev.get("outcome") or "")
        if outcome == "kill":
            kills += 1
        elif outcome == "loss":
            losses += 1
    return {"kills": kills, "losses": losses}


async def sync_killboard(
    session: AsyncSession,
    *,
    scope: str = "alliance",
    scope_id: int | None = None,
    period_days: int = 30,
) -> dict[str, Any]:
    """Refresh killboard rows from zKill + in-game combat snapshots."""
    if scope not in {"alliance", "corp"}:
        scope = "alliance"
    if scope_id is None:
        scope_id = (
            settings.killboard_alliance_id if scope == "alliance" else settings.killboard_corporation_id
        )

    scope_stats = await fetch_scope_stats(scope, int(scope_id))
    roster_names = await _scope_member_ids(session, scope, int(scope_id))
    candidate_names: dict[int, str] = dict(roster_names)
    for cid, name in _top_characters_from_scope_stats(scope_stats):
        candidate_names.setdefault(cid, name)

    if not candidate_names:
        await session.execute(
            delete(KillboardLeaderboard).where(
                KillboardLeaderboard.scope == scope,
                KillboardLeaderboard.scope_id == int(scope_id),
            )
        )
        return {"scope": scope, "scope_id": scope_id, "characters": 0, "rows": 0}

    profiles = (
        await session.scalars(
            select(AuditProfile).where(AuditProfile.character_id.in_(list(candidate_names.keys())))
        )
    ).all()
    profile_map = {int(p.character_id): p for p in profiles}

    aggregated: dict[int, dict[str, Any]] = {}
    char_ids = list(candidate_names.keys())
    for i in range(0, len(char_ids), 5):
        batch = char_ids[i : i + 5]
        results = await asyncio.gather(
            *[fetch_character_stats(cid) for cid in batch],
            return_exceptions=True,
        )
        for cid, result in zip(batch, results):
            if isinstance(result, Exception):
                logger.warning("zkill stats failed for %s: %s", cid, result)
                continue
            if result.get("error"):
                continue
            raw = result.get("raw") or {}
            stats = _stats_for_period(raw, period_days)
            aggregated[cid] = {
                "character_id": cid,
                "character_name": candidate_names.get(cid, f"Character {cid}"),
                "kills": int(stats["kills"]),
                "losses": int(stats["losses"]),
                "isk_destroyed": Decimal(str(stats["isk_destroyed"])),
                "isk_lost": Decimal(str(stats["isk_lost"])),
                "source": "zkill",
            }
        if i + 5 < len(char_ids):
            await asyncio.sleep(0.25)

    for cid, name in candidate_names.items():
        profile = profile_map.get(cid)
        if not profile:
            continue
        combat = _combat_totals(load_snapshot(profile), period_days=period_days)
        if combat["kills"] == 0 and combat["losses"] == 0:
            continue
        row = aggregated.get(cid)
        if row:
            row["kills"] = max(int(row["kills"]), combat["kills"])
            row["losses"] = max(int(row["losses"]), combat["losses"])
            row["source"] = "zkill+ingame"
        else:
            aggregated[cid] = {
                "character_id": cid,
                "character_name": name,
                "kills": combat["kills"],
                "losses": combat["losses"],
                "isk_destroyed": Decimal("0"),
                "isk_lost": Decimal("0"),
                "source": "ingame",
            }

    await session.execute(
        delete(KillboardLeaderboard).where(
            KillboardLeaderboard.scope == scope,
            KillboardLeaderboard.scope_id == int(scope_id),
        )
    )

    rows_written = 0
    for row in sorted(aggregated.values(), key=lambda r: float(r["isk_destroyed"]), reverse=True):
        if row["kills"] == 0 and row["losses"] == 0:
            continue
        session.add(
            KillboardLeaderboard(
                scope=scope,
                scope_id=int(scope_id),
                period_days=period_days,
                character_id=int(row["character_id"]),
                character_name=str(row["character_name"]),
                kills=int(row["kills"]),
                losses=int(row["losses"]),
                isk_destroyed=row["isk_destroyed"],
                isk_lost=row["isk_lost"],
            )
        )
        rows_written += 1

    return {
        "scope": scope,
        "scope_id": scope_id,
        "period_days": period_days,
        "characters": len(candidate_names),
        "rows": rows_written,
        "alliance_isk_destroyed": scope_stats.get("isk_destroyed"),
        "alliance_ships_destroyed": scope_stats.get("ships_destroyed"),
    }


async def killboard_is_stale(session: AsyncSession, scope: str, scope_id: int) -> bool:
    row = await session.scalar(
        select(KillboardLeaderboard)
        .where(KillboardLeaderboard.scope == scope, KillboardLeaderboard.scope_id == scope_id)
        .order_by(KillboardLeaderboard.updated_at.desc())
        .limit(1)
    )
    if row is None:
        return True
    updated = row.updated_at
    if updated is None:
        return True
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return datetime.now(UTC) - updated > timedelta(hours=_STALE_HOURS)


def _parse_kill_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (TypeError, ValueError):
        return None


def _classify_outcome(
    row: dict[str, Any],
    *,
    roster_ids: set[int],
    scope: str,
    scope_id: int,
) -> str:
    victim_id = int(row.get("victim_character_id") or 0)
    if victim_id in roster_ids:
        return "loss"
    victim_alliance = int(row.get("victim_alliance_id") or 0)
    victim_corp = int(row.get("victim_corporation_id") or 0)
    if scope == "alliance" and victim_alliance == scope_id:
        return "loss"
    if scope == "corp" and victim_corp == scope_id:
        return "loss"

    for atk in row.get("attackers") or []:
        if not isinstance(atk, dict):
            continue
        cid = int(atk.get("character_id") or 0)
        if cid in roster_ids:
            return "kill"
        if scope == "alliance" and int(atk.get("alliance_id") or 0) == scope_id:
            return "kill"
        if scope == "corp" and int(atk.get("corporation_id") or 0) == scope_id:
            return "kill"
    return "kill"


def _primary_pilot_id(row: dict[str, Any], *, roster_ids: set[int], outcome: str) -> int | None:
    if outcome == "loss":
        vid = int(row.get("victim_character_id") or 0)
        return vid or None
    scope_attackers = [
        atk
        for atk in row.get("attackers") or []
        if isinstance(atk, dict) and int(atk.get("character_id") or 0) in roster_ids
    ]
    if not scope_attackers:
        for atk in row.get("attackers") or []:
            if isinstance(atk, dict) and int(atk.get("character_id") or 0) > 0:
                scope_attackers.append(atk)
    if not scope_attackers:
        return None
    final = next((a for a in scope_attackers if a.get("final_blow")), None)
    pick = final or max(scope_attackers, key=lambda a: int(a.get("damage_done") or 0))
    cid = int(pick.get("character_id") or 0)
    return cid or None


def _combat_event_to_row(ev: dict[str, Any], *, roster_names: dict[int, str]) -> dict[str, Any]:
    outcome = str(ev.get("outcome") or "kill")
    victim_id = int(ev.get("victim_character_id") or 0) or None
    attacker_ids = [
        int(x) for x in (ev.get("attacker_character_ids") or []) if int(x) > 0
    ]
    attackers = [
        {"character_id": cid, "final_blow": False, "damage_done": 0}
        for cid in attacker_ids
    ]
    pilot_id = victim_id if outcome == "loss" else (attacker_ids[0] if attacker_ids else None)
    return {
        "killmail_id": int(ev.get("killmail_id") or 0),
        "killmail_hash": str(ev.get("killmail_hash") or ""),
        "killed_at": ev.get("killed_at"),
        "solar_system_id": ev.get("solar_system_id"),
        "solar_system_name": ev.get("solar_system_name"),
        "ship_type_id": ev.get("ship_type_id"),
        "ship_type_name": ev.get("ship_type_name"),
        "total_value": 0.0,
        "outcome": outcome,
        "victim_character_id": victim_id,
        "victim_character_name": ev.get("victim_character_name"),
        "pilot_character_id": pilot_id,
        "pilot_character_name": (
            roster_names.get(int(pilot_id), ev.get("victim_character_name"))
            if pilot_id
            else None
        ),
        "attackers": attackers,
        "zkill_url": ev.get("zkill_url") or f"https://zkillboard.com/kill/{ev.get('killmail_id')}/",
        "source": "ingame",
    }


async def _enrich_kill_rows(
    session: AsyncSession,
    rows: list[dict[str, Any]],
    *,
    roster_names: dict[int, str],
) -> list[dict[str, Any]]:
    type_ids: set[int] = set()
    char_ids: set[int] = set()
    system_ids: set[int] = set()
    for row in rows:
        sid = row.get("ship_type_id")
        if sid:
            type_ids.add(int(sid))
        vid = row.get("victim_character_id")
        if vid:
            char_ids.add(int(vid))
        pid = row.get("pilot_character_id")
        if pid:
            char_ids.add(int(pid))
        sys_id = row.get("solar_system_id")
        if sys_id:
            system_ids.add(int(sys_id))
        for atk in row.get("attackers") or []:
            if isinstance(atk, dict):
                cid = atk.get("character_id")
                if cid:
                    char_ids.add(int(cid))

    type_names: dict[int, str] = {}
    if type_ids:
        sde_rows = await session.scalars(select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(type_ids)))
        type_names = {int(r.type_id): r.name for r in sde_rows.all()}

    name_ids = list(char_ids | system_ids)
    resolved = await resolve_universe_names(name_ids) if name_ids else {}

    out: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        ship_id = enriched.get("ship_type_id")
        if ship_id and not enriched.get("ship_type_name"):
            enriched["ship_type_name"] = type_names.get(int(ship_id), f"Type {ship_id}")
        vid = enriched.get("victim_character_id")
        if vid and not enriched.get("victim_character_name"):
            enriched["victim_character_name"] = roster_names.get(int(vid)) or resolved.get(int(vid), f"Character {vid}")
        pid = enriched.get("pilot_character_id")
        if pid and not enriched.get("pilot_character_name"):
            enriched["pilot_character_name"] = roster_names.get(int(pid)) or resolved.get(int(pid), f"Character {pid}")
        sys_id = enriched.get("solar_system_id")
        if sys_id and not enriched.get("solar_system_name"):
            enriched["solar_system_name"] = resolved.get(int(sys_id), f"System {sys_id}")

        attackers_out: list[dict[str, Any]] = []
        for atk in enriched.get("attackers") or []:
            if not isinstance(atk, dict):
                continue
            cid = atk.get("character_id")
            attackers_out.append(
                {
                    **atk,
                    "character_name": (
                        roster_names.get(int(cid)) or resolved.get(int(cid), f"Character {cid}")
                        if cid
                        else None
                    ),
                }
            )
        enriched["attackers"] = attackers_out
        out.append(enriched)
    return out


def _merge_kill_rows(*sources: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    by_id: dict[int, dict[str, Any]] = {}
    for source in sources:
        for row in source:
            km_id = int(row.get("killmail_id") or 0)
            if km_id <= 0:
                continue
            existing = by_id.get(km_id)
            if existing is None:
                by_id[km_id] = row
                continue
            if float(row.get("total_value") or 0) > float(existing.get("total_value") or 0):
                by_id[km_id] = {**existing, **row}
            else:
                by_id[km_id] = {**row, **existing}

    merged = list(by_id.values())
    merged.sort(
        key=lambda r: _parse_kill_time(r.get("killed_at")) or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    return merged[:limit]


async def get_recent_kills(
    session: AsyncSession,
    *,
    scope: str = "alliance",
    scope_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if scope not in {"alliance", "corp"}:
        scope = "alliance"
    if scope_id is None:
        scope_id = (
            settings.killboard_alliance_id if scope == "alliance" else settings.killboard_corporation_id
        )

    roster_names = await _scope_member_ids(session, scope, int(scope_id))
    roster_ids = set(roster_names.keys())

    zkill_rows = await fetch_scope_recent_kills(scope, int(scope_id), limit=limit)
    normalized: list[dict[str, Any]] = []
    for raw in zkill_rows:
        outcome = _classify_outcome(
            raw, roster_ids=roster_ids, scope=scope, scope_id=int(scope_id)
        )
        pilot_id = _primary_pilot_id(raw, roster_ids=roster_ids, outcome=outcome)
        normalized.append(
            {
                **raw,
                "outcome": outcome,
                "pilot_character_id": pilot_id,
                "source": "zkill",
            }
        )

    combat_rows: list[dict[str, Any]] = []
    if roster_ids:
        profiles = (
            await session.scalars(
                select(AuditProfile).where(AuditProfile.character_id.in_(list(roster_ids)))
            )
        ).all()
        for profile in profiles:
            events = load_snapshot(profile).get("combat_log") or []
            for ev in events:
                if isinstance(ev, dict):
                    combat_rows.append(_combat_event_to_row(ev, roster_names=roster_names))

    merged = _merge_kill_rows(normalized, combat_rows, limit=limit)
    return await _enrich_kill_rows(session, merged, roster_names=roster_names)


async def get_pilot_killboard_detail(
    session: AsyncSession,
    character_id: int,
    *,
    scope: str = "alliance",
    scope_id: int | None = None,
    recent_limit: int = 20,
) -> dict[str, Any]:
    if scope_id is None:
        scope_id = (
            settings.killboard_alliance_id if scope == "alliance" else settings.killboard_corporation_id
        )

    roster_names = await _scope_member_ids(session, scope, int(scope_id))
    name = roster_names.get(character_id)
    if not name:
        resolved = await resolve_universe_names([character_id])
        name = resolved.get(character_id, f"Character {character_id}")

    lb_row = await session.scalar(
        select(KillboardLeaderboard)
        .where(
            KillboardLeaderboard.scope == scope,
            KillboardLeaderboard.scope_id == int(scope_id),
            KillboardLeaderboard.character_id == character_id,
        )
        .limit(1)
    )

    zkill = await fetch_character_stats(character_id)
    recent_raw = await fetch_character_recent_kills(character_id, limit=recent_limit)
    recent_norm: list[dict[str, Any]] = []
    roster_ids = set(roster_names.keys())
    for raw in recent_raw:
        outcome = _classify_outcome(
            raw, roster_ids=roster_ids, scope=scope, scope_id=int(scope_id)
        )
        if raw.get("victim_character_id") == character_id:
            outcome = "loss"
        elif any(
            int(a.get("character_id") or 0) == character_id
            for a in raw.get("attackers") or []
            if isinstance(a, dict)
        ):
            outcome = "kill"
        pilot_id = character_id
        recent_norm.append(
            {
                **raw,
                "outcome": outcome,
                "pilot_character_id": pilot_id,
                "pilot_character_name": name,
            }
        )

    profile = await session.scalar(
        select(AuditProfile).where(AuditProfile.character_id == character_id).limit(1)
    )
    combat_rows: list[dict[str, Any]] = []
    if profile:
        for ev in load_snapshot(profile).get("combat_log") or []:
            if isinstance(ev, dict):
                combat_rows.append(_combat_event_to_row(ev, roster_names=roster_names))

    recent = await _enrich_kill_rows(
        session,
        _merge_kill_rows(recent_norm, combat_rows, limit=recent_limit),
        roster_names=roster_names,
    )

    kills = int(lb_row.kills) if lb_row else int(zkill.get("ships_destroyed") or 0)
    losses = int(lb_row.losses) if lb_row else int(zkill.get("ships_lost") or 0)
    isk_destroyed = float(lb_row.isk_destroyed) if lb_row else float(zkill.get("isk_destroyed") or 0)
    isk_lost = float(lb_row.isk_lost) if lb_row else float(zkill.get("isk_lost") or 0)

    return {
        "character_id": character_id,
        "character_name": name,
        "kills": kills,
        "losses": losses,
        "isk_destroyed": isk_destroyed,
        "isk_lost": isk_lost,
        "recent_kills": recent,
        "in_roster": character_id in roster_names,
        "zkill_url": f"https://zkillboard.com/character/{character_id}/",
    }
