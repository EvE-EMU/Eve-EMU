from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.config import settings
from app.services.browser import (
    item_orders,
    listed_types_catalog,
    listed_types_category_tree,
    resolve_type_id,
    search_listed_types,
)

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
    """Market-group tree of listed items (expandable category browser)."""
    return await listed_types_category_tree(location_id=_location_id(location_id))


@router.get("/search")
async def browser_search(
    q: str = Query("", max_length=120),
    limit: int = Query(40, ge=1, le=200),
    location_id: int | None = None,
) -> dict:
    loc = _location_id(location_id)
    types = await search_listed_types(location_id=loc, query=q, limit=limit)
    return {"location_id": loc, "query": q, "types": types}


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
        raise HTTPException(404, f"No listed item matching '{name}' at this hub")
    return await item_orders(location_id=loc, type_id=tid)
