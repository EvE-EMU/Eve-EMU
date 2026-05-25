"""Trade volume by type — regional ESI history aggregates (Adam4EVE tradeVol_type)."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from sqlalchemy import func, select

from app.config import settings
from app.db.models import MarketHistoryDay, MarketType
from app.db.session import session_scope
from app.services.browser import listed_types_catalog
from app.services.catalog import catalog_type_name
from app.services.market_history import resolve_hub_region_id, sync_type_history

logger = logging.getLogger(__name__)

_history_task: asyncio.Task | None = None

_COMPARE_REGIONS: dict[str, tuple[int, str]] = {
    "jita": (10000002, "Jita (The Forge)"),
    "amarr": (10000043, "Amarr (Domain)"),
}


def history_sync_running() -> bool:
    return _history_task is not None and not _history_task.done()


def _compare_region(compare: str) -> tuple[int, str]:
    key = (compare or "jita").lower()
    if key in _COMPARE_REGIONS:
        return _COMPARE_REGIONS[key]
    return (
        int(settings.default_import_region_id),
        "Jita (The Forge)",
    )


async def _aggregate_volumes(
    *,
    region_id: int,
    type_ids: list[int],
    since: date,
) -> dict[int, dict]:
    if not type_ids:
        return {}
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(
                    MarketHistoryDay.type_id,
                    func.sum(MarketHistoryDay.volume).label("volume"),
                    func.sum(MarketHistoryDay.volume * MarketHistoryDay.average).label(
                        "isk_volume"
                    ),
                    func.avg(MarketHistoryDay.average).label("avg_price"),
                    func.sum(MarketHistoryDay.order_count).label("order_count"),
                    func.count().label("days"),
                )
                .where(
                    MarketHistoryDay.region_id == region_id,
                    MarketHistoryDay.type_id.in_(type_ids),
                    MarketHistoryDay.day >= since,
                )
                .group_by(MarketHistoryDay.type_id)
            )
        ).all()

    out: dict[int, dict] = {}
    for r in rows:
        tid = int(r.type_id)
        vol = int(r.volume or 0)
        out[tid] = {
            "volume": vol,
            "isk_volume": float(r.isk_volume or 0),
            "avg_price": round(float(r.avg_price or 0), 2) if r.avg_price else None,
            "order_count": int(r.order_count or 0),
            "days_with_data": int(r.days or 0),
            "avg_daily_volume": round(vol / max(int(r.days or 1), 1), 1),
        }
    return out


async def _type_names(location_id: int, type_ids: list[int]) -> dict[int, str]:
    names: dict[int, str] = {}
    if not type_ids:
        return names
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(MarketType.type_id, MarketType.name).where(
                    MarketType.location_id == location_id,
                    MarketType.type_id.in_(type_ids),
                )
            )
        ).all()
    for r in rows:
        if r.name and str(r.name).strip():
            names[int(r.type_id)] = str(r.name).strip()
    for tid in type_ids:
        if tid not in names:
            label = await catalog_type_name(tid)
            if label:
                names[tid] = label
    return names


async def trade_volume_rows(
    *,
    location_id: int,
    days: int = 30,
    compare: str = "jita",
    limit: int = 500,
    listed_only: bool = True,
) -> dict:
    days = max(7, min(days, 365))
    since = date.today() - timedelta(days=days)
    hub_rid = await resolve_hub_region_id()
    cmp_rid, cmp_label = _compare_region(compare)

    catalog = await listed_types_catalog(location_id=location_id)
    types = catalog.get("types") or []
    if not listed_only:
        types = types  # noqa: kept for future catalog-wide mode
    type_ids = [int(t["type_id"]) for t in types]
    names = await _type_names(location_id, type_ids)

    hub_vol = await _aggregate_volumes(
        region_id=hub_rid, type_ids=type_ids, since=since
    )
    cmp_vol = await _aggregate_volumes(
        region_id=cmp_rid, type_ids=type_ids, since=since
    )

    missing_hub = sum(1 for tid in type_ids if tid not in hub_vol)
    if type_ids and missing_hub > len(type_ids) * 0.25:
        schedule_history_sync(location_id=location_id, max_types=400)

    rows: list[dict] = []
    for tid in type_ids:
        h = hub_vol.get(tid, {})
        c = cmp_vol.get(tid, {})
        hub_v = int(h.get("volume") or 0)
        cmp_v = int(c.get("volume") or 0)
        if hub_v == 0 and cmp_v == 0:
            continue
        rows.append(
            {
                "type_id": tid,
                "type_name": names.get(tid) or f"Type {tid}",
                "hub_volume": hub_v,
                "hub_isk_volume": round(float(h.get("isk_volume") or 0), 2),
                "hub_avg_price": h.get("avg_price"),
                "hub_avg_daily_volume": h.get("avg_daily_volume", 0),
                "hub_days": h.get("days_with_data", 0),
                "compare_volume": cmp_v,
                "compare_isk_volume": round(float(c.get("isk_volume") or 0), 2),
                "compare_avg_price": c.get("avg_price"),
                "compare_avg_daily_volume": c.get("avg_daily_volume", 0),
                "compare_days": c.get("days_with_data", 0),
                "volume_ratio": round(hub_v / cmp_v, 3) if cmp_v > 0 else None,
            }
        )

    rows.sort(key=lambda r: r["hub_volume"], reverse=True)
    rows = rows[:limit]

    hub_region_label = (
        f"{settings.wompstar_structure_name or '3-F hub'} region ({hub_rid})"
    )

    return {
        "location_id": location_id,
        "location_name": settings.wompstar_structure_name,
        "days": days,
        "since": since.isoformat(),
        "hub_region_id": hub_rid,
        "hub_region_label": hub_region_label,
        "compare_region_id": cmp_rid,
        "compare_label": cmp_label,
        "compare_hub": compare,
        "type_count": len(type_ids),
        "rows_with_volume": len(rows),
        "history_sync_running": history_sync_running(),
        "history_pending": missing_hub > 0,
        "rows": rows,
    }


async def sync_history_for_types(
    type_ids: list[int],
    *,
    region_ids: list[int],
    max_types: int = 400,
) -> dict[str, int]:
    """Pull ESI regional history for listed types (rate-limited)."""
    sem = asyncio.Semaphore(max(2, settings.esi_max_concurrent))
    tids = type_ids[:max_types]
    updated = 0
    errors = 0

    async def _one(tid: int, rid: int) -> None:
        nonlocal updated, errors
        async with sem:
            try:
                n = await sync_type_history(region_id=rid, type_id=tid)
                if n:
                    updated += 1
            except Exception:
                errors += 1
                logger.exception("history sync failed type=%s region=%s", tid, rid)

    tasks = []
    for tid in tids:
        for rid in region_ids:
            tasks.append(_one(tid, rid))
    await asyncio.gather(*tasks)
    return {"types": len(tids), "regions": len(region_ids), "updated": updated, "errors": errors}


async def _run_history_job(location_id: int) -> None:
    global _history_task
    try:
        hub_rid = await resolve_hub_region_id()
        cmp_rid, _ = _compare_region("jita")
        catalog = await listed_types_catalog(location_id=location_id)
        type_ids = [int(t["type_id"]) for t in (catalog.get("types") or [])]
        stats = await sync_history_for_types(
            type_ids,
            region_ids=[hub_rid, cmp_rid],
            max_types=500,
        )
        logger.info("history bulk sync: %s", stats)
    except Exception:
        logger.exception("history bulk sync failed")
    finally:
        _history_task = None


def schedule_history_sync(*, location_id: int, max_types: int = 400) -> None:
    global _history_task
    if history_sync_running():
        return
    _history_task = asyncio.create_task(_run_history_job(location_id))
