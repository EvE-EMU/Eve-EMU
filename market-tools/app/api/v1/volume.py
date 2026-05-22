from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.services.trade_volume import (
    history_sync_running,
    schedule_history_sync,
    sync_history_for_types,
    trade_volume_rows,
)
from app.services.browser import listed_types_catalog
from app.services.market_history import resolve_hub_region_id

router = APIRouter()


def _location_id(location_id: int | None) -> int:
    loc = location_id or settings.wompstar_structure_id
    if not loc:
        raise HTTPException(503, "WOMPSTAR structure not configured")
    return int(loc)


@router.get("/types")
async def volume_by_type(
    location_id: int | None = None,
    days: int = Query(30, ge=7, le=365),
    compare: str = Query("jita", pattern="^(jita|amarr)$"),
    limit: int = Query(500, ge=1, le=2000),
) -> dict:
    """Regional trade volume by type (default last 30 days)."""
    return await trade_volume_rows(
        location_id=_location_id(location_id),
        days=days,
        compare=compare,
        limit=limit,
    )


@router.get("/status")
async def volume_sync_status() -> dict:
    return {"history_sync_running": history_sync_running()}


@router.post("/sync")
async def trigger_history_sync(location_id: int | None = None) -> dict:
    loc = _location_id(location_id)
    if history_sync_running():
        return {"status": "already_running"}
    schedule_history_sync(location_id=loc)
    return {"status": "started", "location_id": loc}


@router.post("/sync/now")
async def history_sync_now(
    location_id: int | None = None,
    max_types: int = Query(200, ge=1, le=500),
) -> dict:
    """Synchronous history pull (slow; prefer POST /sync)."""
    loc = _location_id(location_id)
    hub_rid = await resolve_hub_region_id()
    from app.services.trade_volume import _compare_region

    cmp_rid, _ = _compare_region("jita")
    catalog = await listed_types_catalog(location_id=loc)
    type_ids = [int(t["type_id"]) for t in (catalog.get("types") or [])]
    stats = await sync_history_for_types(
        type_ids,
        region_ids=[hub_rid, cmp_rid],
        max_types=max_types,
    )
    return {"status": "ok", **stats}
