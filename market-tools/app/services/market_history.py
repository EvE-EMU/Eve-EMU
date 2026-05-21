"""Region market history from public ESI (cached in Postgres)."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx
from sqlalchemy import delete, select

from app.config import settings
from app.db.models import MarketHistoryDay
from app.db.session import session_scope
from app.esi.rate_limit import acquire_slot

logger = logging.getLogger(__name__)
_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-Market/1.0"

_region_cache: int | None = None


async def resolve_hub_region_id() -> int:
    """Region for 3-FKCZ / WOMPSTAR (system → region via public ESI)."""
    global _region_cache
    if _region_cache:
        return _region_cache
    configured = int(settings.wompstar_region_id or 0)
    if configured and configured != 10000001:
        _region_cache = configured
        return _region_cache

    system_id = int(getattr(settings, "wompstar_system_id", 0) or 30004019)
    await acquire_slot()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{_ESI}/universe/systems/{system_id}/",
            headers={"Accept": "application/json", "User-Agent": _UA},
        )
    if resp.status_code == 200:
        body = resp.json()
        if isinstance(body, dict) and body.get("region_id"):
            _region_cache = int(body["region_id"])
            return _region_cache

    _region_cache = configured or 10000050
    return _region_cache


async def _fetch_esi_history(*, region_id: int, type_id: int) -> list[dict]:
    await acquire_slot()
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.get(
            f"{_ESI}/markets/{region_id}/history/",
            params={"type_id": type_id},
            headers={"Accept": "application/json", "User-Agent": _UA},
        )
    if resp.status_code != 200:
        logger.warning(
            "market history %s type %s: %s",
            region_id,
            type_id,
            resp.status_code,
        )
        return []
    data = resp.json()
    return data if isinstance(data, list) else []


async def sync_type_history(*, region_id: int, type_id: int) -> int:
    rows_raw = await _fetch_esi_history(region_id=region_id, type_id=type_id)
    if not rows_raw:
        return 0

    rows: list[dict] = []
    for r in rows_raw:
        if not isinstance(r, dict):
            continue
        raw_day = r.get("date")
        if not raw_day:
            continue
        try:
            day = date.fromisoformat(str(raw_day)[:10])
        except ValueError:
            continue
        rows.append(
            {
                "type_id": type_id,
                "region_id": region_id,
                "day": day,
                "average": float(r.get("average") or 0),
                "highest": float(r.get("highest") or 0),
                "lowest": float(r.get("lowest") or 0),
                "volume": int(r.get("volume") or 0),
                "order_count": int(r.get("order_count") or 0),
            }
        )

    if not rows:
        return 0

    async with session_scope() as session:
        await session.execute(
            delete(MarketHistoryDay).where(
                MarketHistoryDay.type_id == type_id,
                MarketHistoryDay.region_id == region_id,
            )
        )
        session.add_all([MarketHistoryDay(**r) for r in rows])

    return len(rows)


async def type_history(
    *,
    type_id: int,
    region_id: int | None = None,
    max_days: int = 180,
) -> dict:
    rid = region_id or await resolve_hub_region_id()
    cutoff = date.today() - timedelta(days=max_days)

    async with session_scope() as session:
        cached = (
            await session.execute(
                select(MarketHistoryDay)
                .where(
                    MarketHistoryDay.type_id == type_id,
                    MarketHistoryDay.region_id == rid,
                    MarketHistoryDay.day >= cutoff,
                )
                .order_by(MarketHistoryDay.day)
            )
        ).scalars().all()

    if len(cached) < 14:
        await sync_type_history(region_id=rid, type_id=type_id)
        async with session_scope() as session:
            cached = (
                await session.execute(
                    select(MarketHistoryDay)
                    .where(
                        MarketHistoryDay.type_id == type_id,
                        MarketHistoryDay.region_id == rid,
                        MarketHistoryDay.day >= cutoff,
                    )
                    .order_by(MarketHistoryDay.day)
                )
            ).scalars().all()

    days = [
        {
            "day": h.day.isoformat(),
            "average": h.average,
            "highest": h.highest,
            "lowest": h.lowest,
            "volume": h.volume,
            "order_count": h.order_count,
        }
        for h in cached
    ]

    return {
        "region_id": rid,
        "type_id": type_id,
        "max_days": max_days,
        "days": days,
        "note": (
            "Daily regional market history (Querious). "
            "Structure-specific history is not published by ESI; "
            "use live buy/sell tables above for current WOMPSTAR orders."
        ),
    }
