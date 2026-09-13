"""Per-system jump/kill activity — hourly ESI snapshots rolled up to 24h/48h (Dotlan-style)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SdeSystem, SdeSystemActivityHour
from app.services.esi import esi_get

logger = logging.getLogger(__name__)

_last_refresh: datetime | None = None
_REFRESH_MINUTES = 55


def _hour_floor(dt: datetime) -> datetime:
    dt = dt.astimezone(UTC)
    return dt.replace(minute=0, second=0, microsecond=0)


async def _fetch_esi_snapshots() -> dict[int, dict[str, int]]:
    """Merge ESI system_jumps + system_kills into per-system hourly values."""
    status_j, jumps_body = await esi_get("/universe/system_jumps/", params={"datasource": "tranquility"})
    status_k, kills_body = await esi_get("/universe/system_kills/", params={"datasource": "tranquility"})
    if status_j != 200 or not isinstance(jumps_body, list):
        logger.warning("ESI system_jumps failed: %s", status_j)
        jumps_body = []
    if status_k != 200 or not isinstance(kills_body, list):
        logger.warning("ESI system_kills failed: %s", status_k)
        kills_body = []

    merged: dict[int, dict[str, int]] = {}
    for row in jumps_body:
        sid = int(row.get("system_id") or 0)
        if not sid:
            continue
        merged.setdefault(sid, {"ship_jumps": 0, "ship_kills": 0, "pod_kills": 0, "npc_kills": 0})
        merged[sid]["ship_jumps"] = int(row.get("ship_jumps") or 0)
    for row in kills_body:
        sid = int(row.get("system_id") or 0)
        if not sid:
            continue
        merged.setdefault(sid, {"ship_jumps": 0, "ship_kills": 0, "pod_kills": 0, "npc_kills": 0})
        merged[sid]["ship_kills"] = int(row.get("ship_kills") or 0)
        merged[sid]["pod_kills"] = int(row.get("pod_kills") or 0)
        merged[sid]["npc_kills"] = int(row.get("npc_kills") or 0)
    return merged


async def refresh_activity_snapshots(session: AsyncSession, *, force: bool = False) -> dict[str, Any]:
    """Persist current-hour ESI jump/kill counts for all reported systems."""
    global _last_refresh
    now = datetime.now(UTC)
    if (
        not force
        and _last_refresh
        and (now - _last_refresh) < timedelta(minutes=_REFRESH_MINUTES)
    ):
        return {"skipped": True, "last_refresh": _last_refresh.isoformat()}

    merged = await _fetch_esi_snapshots()
    if not merged:
        return {"error": "esi_unavailable", "systems": 0}

    hour_ts = _hour_floor(now)
    rows = [
        {
            "system_id": sid,
            "hour_ts": hour_ts,
            "ship_jumps": vals["ship_jumps"],
            "ship_kills": vals["ship_kills"],
            "pod_kills": vals["pod_kills"],
            "npc_kills": vals["npc_kills"],
        }
        for sid, vals in merged.items()
    ]

    # Upsert in batches (Postgres/SQLite compatible via delete+insert for hour)
    await session.execute(delete(SdeSystemActivityHour).where(SdeSystemActivityHour.hour_ts == hour_ts))
    batch: list[SdeSystemActivityHour] = []
    for row in rows:
        batch.append(SdeSystemActivityHour(**row))
        if len(batch) >= 500:
            session.add_all(batch)
            await session.flush()
            batch.clear()
    if batch:
        session.add_all(batch)
        await session.flush()

    # Drop snapshots older than 72h
    cutoff = now - timedelta(hours=72)
    await session.execute(delete(SdeSystemActivityHour).where(SdeSystemActivityHour.hour_ts < cutoff))

    _last_refresh = now
    logger.info("EMUMS: stored system activity snapshot — %s systems @ %s", len(rows), hour_ts.isoformat())
    return {"systems": len(rows), "hour_ts": hour_ts.isoformat(), "skipped": False}


async def get_system_activity(
    session: AsyncSession,
    system_ids: list[int],
) -> dict[str, Any]:
    """Dotlan-style 24h/48h jumps and kills for requested systems."""
    if not system_ids:
        return {"systems": [], "hours_available": 0}

    await refresh_activity_snapshots(session)

    now = datetime.now(UTC)
    cutoff_48 = now - timedelta(hours=48)
    cutoff_24 = now - timedelta(hours=24)

    hours_available = await session.scalar(
        select(func.count(func.distinct(SdeSystemActivityHour.hour_ts))).where(
            SdeSystemActivityHour.hour_ts >= cutoff_48
        )
    )
    hours_available = int(hours_available or 0)

    rows = (
        await session.scalars(
            select(SdeSystemActivityHour).where(
                SdeSystemActivityHour.system_id.in_(system_ids),
                SdeSystemActivityHour.hour_ts >= cutoff_48,
            )
        )
    ).all()

    agg: dict[int, dict[str, int]] = {
        sid: {
            "jumps_24h": 0,
            "kills_24h": 0,
            "jumps_48h": 0,
            "kills_48h": 0,
            "npc_kills_24h": 0,
            "npc_kills_48h": 0,
        }
        for sid in system_ids
    }
    for row in rows:
        bucket = agg.get(row.system_id)
        if not bucket:
            continue
        kills = row.ship_kills + row.pod_kills
        bucket["jumps_48h"] += row.ship_jumps
        bucket["kills_48h"] += kills
        bucket["npc_kills_48h"] += row.npc_kills
        if row.hour_ts >= cutoff_24:
            bucket["jumps_24h"] += row.ship_jumps
            bucket["kills_24h"] += kills
            bucket["npc_kills_24h"] += row.npc_kills

    names: dict[int, str] = {}
    sec: dict[int, float] = {}
    for sys in (await session.scalars(select(SdeSystem).where(SdeSystem.system_id.in_(system_ids)))).all():
        names[sys.system_id] = sys.name
        sec[sys.system_id] = sys.security

    out = []
    for sid in system_ids:
        b = agg[sid]
        out.append(
            {
                "system_id": sid,
                "name": names.get(sid, str(sid)),
                "security": sec.get(sid, 0.0),
                "jumps_24h": b["jumps_24h"],
                "kills_24h": b["kills_24h"],
                "jumps_48h": b["jumps_48h"],
                "kills_48h": b["kills_48h"],
                "npc_kills_24h": b["npc_kills_24h"],
                "npc_kills_48h": b["npc_kills_48h"],
            }
        )

    return {
        "systems": out,
        "hours_available": hours_available,
        "partial": hours_available < 24,
        "updated_at": _last_refresh.isoformat() if _last_refresh else None,
    }
