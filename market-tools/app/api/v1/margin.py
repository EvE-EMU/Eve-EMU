from fastapi import APIRouter, Query

from app.config import settings
from app.services.hub_prices import enrich_rows_with_hubs
from app.services.margin import margin_rows

router = APIRouter()


@router.get("/finder")
async def margin_finder(
    location_id: int | None = None,
    min_trades: int = Query(1, ge=0),
    min_isk_volume: float = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    loc = location_id or settings.wompstar_structure_id
    if not loc:
        return {"rows": [], "error": "structure_id required"}
    rows = await margin_rows(
        location_id=int(loc),
        min_trades=min_trades,
        min_isk_volume=min_isk_volume,
        limit=limit,
    )
    await enrich_rows_with_hubs(rows)
    return {
        "location_id": loc,
        "location_name": settings.wompstar_structure_name,
        "rows": rows,
    }
