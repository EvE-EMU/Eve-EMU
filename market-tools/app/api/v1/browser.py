from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse, Response

from app.config import settings
from app.services.browser import (
    SUMMARY_CSV_FIELDS,
    item_orders,
    item_summary_csv_text,
    item_summary_row,
    listed_types_catalog,
    listed_types_category_tree,
    market_tree_build,
    resolve_type_id,
    search_types,
)
from app.services.catalog import group_types

router = APIRouter()


@router.get("/icon/{type_id}")
async def type_icon_redirect(type_id: int, size: int = Query(32, ge=8, le=256)) -> RedirectResponse:
    """Redirect to EVE Tech type icon (fallback handled in the browser)."""
    return RedirectResponse(
        url=f"https://images.evetech.net/types/{type_id}/icon?size={size}",
        status_code=302,
    )


def _location_id(location_id: int | None) -> int:
    loc = location_id or settings.wompstar_structure_id
    if not loc:
        raise HTTPException(503, "WOMPSTAR structure not configured")
    return int(loc)


@router.get("/catalog")
async def browser_catalog(location_id: int | None = None) -> dict:
    """All item types currently listed at WOMPSTAR (names + best prices)."""
    return await listed_types_catalog(location_id=_location_id(location_id))


@router.get("/categories")
async def browser_categories(location_id: int | None = None) -> dict:
    """Market-group tree of listed items (orders-only, legacy)."""
    return await listed_types_category_tree(location_id=_location_id(location_id))


@router.get("/tree")
async def browser_tree(
    location_id: int | None = None,
    listed_only: bool = False,
) -> dict:
    """Market group tree (full catalog); optional listed-only filter."""
    return await market_tree_build(
        location_id=_location_id(location_id),
        listed_only=listed_only,
    )


@router.get("/group/{group_id}/types")
async def browser_group_types(
    group_id: int,
    location_id: int | None = None,
    listed_only: bool = False,
) -> dict:
    """Types in a market group (lazy-loaded sidebar)."""
    loc = _location_id(location_id)
    types = await group_types(
        group_id=group_id,
        location_id=loc,
        listed_only=listed_only,
    )
    return {"location_id": loc, "group_id": group_id, "types": types}


@router.get("/search")
async def browser_search(
    q: str = Query("", max_length=120),
    limit: int = Query(40, ge=1, le=200),
    location_id: int | None = None,
    listed_only: bool = False,
) -> dict:
    loc = _location_id(location_id)
    types = await search_types(
        location_id=loc, query=q, limit=limit, listed_only=listed_only
    )
    return {"location_id": loc, "query": q, "listed_only": listed_only, "types": types}


def _csv_response(body: str) -> Response:
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/item/{type_id}/summary.csv")
async def browser_item_summary_csv(
    type_id: int,
    location_id: int | None = None,
    days: int = Query(30, ge=7, le=180, description="Days for regional avg/high/low/volume"),
) -> Response:
    """Single-row CSV for Google Sheets =IMPORTDATA(url)."""
    loc = _location_id(location_id)
    row = await item_summary_row(location_id=loc, type_id=type_id, period_days=days)
    return _csv_response(item_summary_csv_text(row))


@router.get("/item/{type_id}/value.csv")
async def browser_item_value_csv(
    type_id: int,
    field: str = Query(
        "avg_price_30d",
        description=f"One of: {', '.join(SUMMARY_CSV_FIELDS)}",
    ),
    location_id: int | None = None,
    days: int = Query(30, ge=7, le=180),
) -> Response:
    """Two-row, one-column CSV for a single metric (simplest IMPORTDATA)."""
    if field not in SUMMARY_CSV_FIELDS:
        raise HTTPException(
            400,
            f"Unknown field '{field}'. Use one of: {', '.join(SUMMARY_CSV_FIELDS)}",
        )
    loc = _location_id(location_id)
    row = await item_summary_row(location_id=loc, type_id=type_id, period_days=days)
    val = row.get(field)
    body = f"{field}\n{'' if val is None else val}\n"
    return _csv_response(body)


@router.get("/item/value.csv")
async def browser_item_value_csv_by_name(
    name: str = Query(..., min_length=1, max_length=120),
    type_id: int | None = None,
    field: str = Query("avg_price_30d"),
    location_id: int | None = None,
    days: int = Query(30, ge=7, le=180),
) -> Response:
    if field not in SUMMARY_CSV_FIELDS:
        raise HTTPException(400, f"Unknown field '{field}'")
    loc = _location_id(location_id)
    tid = await resolve_type_id(location_id=loc, type_id=type_id, name=name)
    if not tid:
        raise HTTPException(404, f"No item matching '{name}'")
    row = await item_summary_row(location_id=loc, type_id=tid, period_days=days)
    val = row.get(field)
    body = f"{field}\n{'' if val is None else val}\n"
    return _csv_response(body)


@router.get("/item/summary.csv")
async def browser_item_summary_csv_by_name(
    name: str = Query(..., min_length=1, max_length=120),
    type_id: int | None = None,
    location_id: int | None = None,
    days: int = Query(30, ge=7, le=180),
) -> Response:
    loc = _location_id(location_id)
    tid = await resolve_type_id(location_id=loc, type_id=type_id, name=name)
    if not tid:
        raise HTTPException(404, f"No item matching '{name}'")
    row = await item_summary_row(location_id=loc, type_id=tid, period_days=days)
    return _csv_response(item_summary_csv_text(row))


@router.get("/item/{type_id}")
async def browser_item(
    type_id: int,
    location_id: int | None = None,
) -> dict:
    return await item_orders(location_id=_location_id(location_id), type_id=type_id)


@router.get("/item")
async def browser_item_by_name(
    name: str = Query(..., min_length=1, max_length=120),
    type_id: int | None = None,
    location_id: int | None = None,
) -> dict:
    loc = _location_id(location_id)
    tid = await resolve_type_id(location_id=loc, type_id=type_id, name=name)
    if not tid:
        raise HTTPException(404, f"No item matching '{name}'")
    return await item_orders(location_id=loc, type_id=tid)
