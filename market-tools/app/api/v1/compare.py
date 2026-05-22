from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.services.compare import price_compare
from app.services.import_prices import import_sync_running, sync_import_prices_for_hub

router = APIRouter()


def _location_id(location_id: int | None) -> int:
    loc = location_id or settings.wompstar_structure_id
    if not loc:
        raise HTTPException(503, "WOMPSTAR structure not configured")
    return int(loc)


@router.get("")
async def compare_list(
    location_id: int | None = None,
    region_id: int | None = None,
    limit: int = Query(500, ge=1, le=2000),
) -> dict:
    """WOMPSTAR vs import hub prices for listed types."""
    return await price_compare(
        location_id=_location_id(location_id),
        limit=limit,
        region_id=region_id,
    )


@router.get("/status")
async def compare_sync_status() -> dict:
    return {"import_sync_running": import_sync_running()}


@router.post("/sync")
async def trigger_import_sync(location_id: int | None = None) -> dict:
    """Refresh Jita/Forge best bid/ask for all types at the hub."""
    loc = _location_id(location_id)
    if import_sync_running():
        return {
            "status": "already_running",
            "message": "Import price sync already in progress.",
        }
    stats = await sync_import_prices_for_hub(location_id=loc)
    return {"status": "ok", **stats}
