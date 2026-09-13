"""Market tracker — hub vs selected system buy/sell spread via Janice + ESI."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SdeSystem, SdeTypeIndex
from app.services.esi import esi_get_paged_list
from app.services.janice import JANICE_MARKETS, janice_configured, janice_price_rows
from app.services.market_browser import ALL_NPC_STATION_IDS, NPC_MARKET_HUBS
from app.services.route_planner import search_systems
from app.services.sde_search import search_types

logger = logging.getLogger(__name__)

# Popular watchlist when no search query (minerals, fuel, common modules).
TOP_25_TYPE_IDS: list[int] = [
    34,
    35,
    36,
    37,
    38,
    39,
    40,
    11399,
    11486,
    11541,
    11540,
    11539,
    11538,
    11537,
    11536,
    11535,
    11534,
    11533,
    11532,
    11531,
    11530,
    11529,
    11528,
    11527,
    11526,
]


async def _type_row(session: AsyncSession, type_id: int) -> dict[str, Any] | None:
    row = await session.get(SdeTypeIndex, type_id)
    if row:
        return {"type_id": row.type_id, "name": row.name}
    return None


async def _system_orders_for_type(
    session: AsyncSession,
    *,
    region_id: int,
    type_id: int,
    station_ids: set[int] | None = None,
) -> tuple[float | None, float | None]:
    rows = await esi_get_paged_list(
        f"/markets/{region_id}/orders/",
        params={"type_id": type_id},
        max_pages=8,
    )
    best_buy: float | None = None
    best_sell: float | None = None
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        loc_id = int(raw.get("location_id") or 0)
        if station_ids and loc_id not in station_ids:
            continue
        price = float(raw.get("price") or 0)
        if raw.get("is_buy_order"):
            best_buy = price if best_buy is None else max(best_buy, price)
        else:
            best_sell = price if best_sell is None else min(best_sell, price)
    return best_buy, best_sell


def _spread_pct(hub_buy: float | None, hub_sell: float | None, local_buy: float | None, local_sell: float | None) -> float | None:
    """Positive spread % = hub sell vs local buy opportunity (rough arbitrage signal)."""
    if hub_sell is None or local_buy is None or local_buy <= 0:
        return None
    return round(((hub_sell - local_buy) / local_buy) * 100, 2)


async def fetch_market_tracker(
    session: AsyncSession,
    *,
    hub: str = "jita",
    system_id: int | None = None,
    system_q: str = "",
    item_q: str = "",
    limit: int = 25,
) -> dict[str, Any]:
    limit = max(1, min(limit, 50))
    hub = hub.lower()
    hub_label = JANICE_MARKETS.get(hub, JANICE_MARKETS["jita"])[1]

    system_label = "All NPC hub stations"
    region_id: int | None = NPC_MARKET_HUBS["jita"]["region_id"]
    station_filter: set[int] | None = ALL_NPC_STATION_IDS

    if system_id:
        sys_row = await session.get(SdeSystem, system_id)
        if sys_row:
            system_label = sys_row.name
            region_id = sys_row.region_id
            station_filter = None
    elif system_q.strip():
        matches = await search_systems(session, system_q.strip(), limit=1)
        if matches:
            system_label = matches[0]["name"]
            sys_row = await session.get(SdeSystem, matches[0]["system_id"])
            if sys_row and sys_row.region_id:
                region_id = sys_row.region_id
            station_filter = None

    type_rows: list[dict[str, Any]] = []
    if item_q.strip():
        type_rows = await search_types(session, item_q.strip(), limit=limit)
    else:
        for tid in TOP_25_TYPE_IDS[:limit]:
            row = await _type_row(session, tid)
            if row:
                type_rows.append(row)

    if not type_rows:
        return {
            "hub": hub,
            "hub_label": hub_label,
            "system_label": system_label,
            "system_id": system_id,
            "region_id": region_id,
            "janice_configured": janice_configured(),
            "rows": [],
        }

    names = [r["name"] for r in type_rows]
    hub_prices = await janice_price_rows(names, market=hub) if janice_configured() else {}

    rows: list[dict[str, Any]] = []
    for tr in type_rows:
        tid = tr["type_id"]
        name = tr["name"]
        hp = hub_prices.get(name.upper()) or hub_prices.get(str(tid)) or {}
        hub_buy = hp.get("buy")
        hub_sell = hp.get("sell")

        local_buy: float | None = None
        local_sell: float | None = None
        if region_id:
            local_buy, local_sell = await _system_orders_for_type(
                session,
                region_id=int(region_id),
                type_id=tid,
                station_ids=station_filter,
            )

        spread = _spread_pct(hub_buy, hub_sell, local_buy, local_sell)
        rows.append(
            {
                "type_id": tid,
                "type_name": name,
                "hub_buy": round(hub_buy, 2) if hub_buy is not None else None,
                "hub_sell": round(hub_sell, 2) if hub_sell is not None else None,
                "local_buy": round(local_buy, 2) if local_buy is not None else None,
                "local_sell": round(local_sell, 2) if local_sell is not None else None,
                "spread_pct": spread,
                "location_label": system_label,
            }
        )

    rows.sort(key=lambda r: abs(r["spread_pct"] or 0), reverse=True)

    return {
        "hub": hub,
        "hub_label": hub_label,
        "system_label": system_label,
        "system_id": system_id,
        "region_id": region_id,
        "janice_configured": janice_configured(),
        "rows": rows,
    }
