"""Market browser — NPC station/region orders, structure markets, and history."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AuthedStructure, MarketHistoryDay, SdeTypeIndex, SsoUser
from app.services.a4e import (
    a4e_enabled,
    fetch_region_history,
    fetch_region_prices,
    history_row_to_day,
)
from app.services.esi import esi_get, esi_get_paged_list
from app.services.structure_market_access import resolve_structure_market_character

logger = logging.getLogger(__name__)

# ESI region IDs + primary NPC market stations (location_id in order book).
NPC_MARKET_HUBS: dict[str, dict[str, Any]] = {
    "jita": {
        "region_id": 10000002,
        "region_name": "The Forge",
        "stations": [
            (60003760, "Jita IV - Moon 4 - Caldari Navy Assembly Plant"),
            (60003466, "Perimeter - 0.0% Neutral States Embassy"),
            (60003468, "Ikuchi - 0.0% Neutral States Embassy"),
        ],
    },
    "amarr": {
        "region_id": 10000043,
        "region_name": "Domain",
        "stations": [
            (60008494, "Amarr VIII (Oris) - Emperor Family Academy"),
            (60002134, "Megegrid - 0.0% Amarr Navy Assembly Plant"),
        ],
    },
    "dodixie": {
        "region_id": 10000032,
        "region_name": "Sinq Laison",
        "stations": [(60011866, "Dodixie IX - Moon 20 - Federation Navy Assembly Plant")],
    },
    "rens": {
        "region_id": 10000030,
        "region_name": "Heimatar",
        "stations": [(60004588, "Rens VI - Moon 8 - Brutor Tribe Treasury")],
    },
    "hek": {
        "region_id": 10000042,
        "region_name": "Metropolis",
        "stations": [(60005686, "Hek VIII - Moon 12 - Boundless Creation Factory")],
    },
}

_station_name_cache: dict[int, str] = {}

ALL_NPC_STATION_IDS: set[int] = {
    station_id for hub in NPC_MARKET_HUBS.values() for station_id, _ in hub["stations"]
}

MARKET_HISTORY_CACHE_DAYS = 360
MARKET_HISTORY_STALE_DAYS = 2
MARKET_HISTORY_MIN_ROWS = 14


async def _station_name(station_id: int) -> str:
    if station_id in _station_name_cache:
        return _station_name_cache[station_id]
    for hub in NPC_MARKET_HUBS.values():
        for sid, name in hub["stations"]:
            _station_name_cache[sid] = name
    if station_id in _station_name_cache:
        return _station_name_cache[station_id]
    status, body = await esi_get(f"/universe/stations/{station_id}/")
    if status == 200 and isinstance(body, dict):
        name = str(body.get("name") or station_id)
        _station_name_cache[station_id] = name
        return name
    return str(station_id)


def _normalize_order(raw: dict[str, Any], *, location_label: str) -> dict[str, Any]:
    out = {
        "order_id": raw.get("order_id"),
        "type_id": raw.get("type_id"),
        "location_id": raw.get("location_id"),
        "location_label": location_label,
        "is_buy_order": bool(raw.get("is_buy_order")),
        "price": float(raw.get("price") or 0),
        "volume_remain": int(raw.get("volume_remain") or 0),
        "volume_total": int(raw.get("volume_total") or 0),
        "min_volume": int(raw.get("min_volume") or 1),
        "range": str(raw.get("range") or "station"),
        "issued": raw.get("issued"),
        "duration": int(raw.get("duration") or 0),
    }
    if raw.get("source"):
        out["source"] = raw["source"]
    return out


def _synthetic_top_of_book(
    *,
    type_id: int,
    location_id: int,
    location_label: str,
    buy: float | None,
    sell: float | None,
    buy_volume: int,
    sell_volume: int,
    source: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Single-level bid/ask snapshot from Adam4EVE regional orderbook stats."""
    buy_orders: list[dict[str, Any]] = []
    sell_orders: list[dict[str, Any]] = []
    if buy is not None and buy > 0:
        buy_orders.append(
            _normalize_order(
                {
                    "order_id": None,
                    "type_id": type_id,
                    "location_id": location_id,
                    "is_buy_order": True,
                    "price": buy,
                    "volume_remain": buy_volume,
                    "volume_total": buy_volume,
                    "range": "region",
                    "source": source,
                },
                location_label=location_label,
            )
        )
    if sell is not None and sell > 0:
        sell_orders.append(
            _normalize_order(
                {
                    "order_id": None,
                    "type_id": type_id,
                    "location_id": location_id,
                    "is_buy_order": False,
                    "price": sell,
                    "volume_remain": sell_volume,
                    "volume_total": sell_volume,
                    "range": "region",
                    "source": source,
                },
                location_label=location_label,
            )
        )
    return buy_orders, sell_orders


async def _fetch_npc_orders_a4e(
    *,
    type_id: int,
    location_kind: str,
    location_id: int,
    region_id: int | None,
    location_label: str,
) -> dict[str, Any] | None:
    if not a4e_enabled():
        return None

    buy_orders: list[dict] = []
    sell_orders: list[dict] = []
    source = "adam4eve"

    if location_kind == "all_stations":
        seen: set[int] = set()
        for hub in NPC_MARKET_HUBS.values():
            rid = int(hub["region_id"])
            if rid in seen:
                continue
            seen.add(rid)
            snap = await fetch_region_prices(type_id, region_id=rid)
            if not snap:
                continue
            label = f"{hub['region_name']} (regional top of book)"
            b, s = _synthetic_top_of_book(
                type_id=type_id,
                location_id=rid,
                location_label=label,
                buy=snap.get("buy"),
                sell=snap.get("sell"),
                buy_volume=int(snap.get("buy_volume") or 0),
                sell_volume=int(snap.get("sell_volume") or 0),
                source=source,
            )
            buy_orders.extend(b)
            sell_orders.extend(s)
        if not buy_orders and not sell_orders:
            return None
        buy_orders.sort(key=lambda o: o["price"], reverse=True)
        sell_orders.sort(key=lambda o: o["price"])
        return {
            "buy_orders": buy_orders,
            "sell_orders": sell_orders,
            "location_label": "All trade hubs (Adam4EVE regional snapshots)",
            "region_id": None,
            "data_source": source,
            "data_note": (
                "Top-of-book bid/ask from Adam4EVE regional orderbooks (not full ESI depth). "
                "Player structure markets still use live ESI."
            ),
        }

    rid = region_id or location_id
    if location_kind == "station":
        rid = region_id or _region_for_station(location_id) or rid
        location_label = f"{location_label} — regional snapshot (Adam4EVE)"

    snap = await fetch_region_prices(type_id, region_id=int(rid))
    if not snap:
        return None
    buy_orders, sell_orders = _synthetic_top_of_book(
        type_id=type_id,
        location_id=int(rid),
        location_label=location_label,
        buy=snap.get("buy"),
        sell=snap.get("sell"),
        buy_volume=int(snap.get("buy_volume") or 0),
        sell_volume=int(snap.get("sell_volume") or 0),
        source=source,
    )
    return {
        "buy_orders": buy_orders,
        "sell_orders": sell_orders,
        "location_label": location_label,
        "region_id": int(rid),
        "data_source": source,
        "data_note": (
            "Top-of-book bid/ask from Adam4EVE (orderbook-derived). "
            "Station-level filtering is not available via Adam4EVE; values are regional."
        ),
    }


async def list_market_locations(session: AsyncSession) -> dict[str, Any]:
    npc: list[dict] = [
        {
            "id": "all:stations",
            "slug": "all",
            "kind": "all_stations",
            "region_id": None,
            "name": "All trade hubs (all stations)",
            "station_id": None,
        }
    ]
    for slug, hub in NPC_MARKET_HUBS.items():
        region_id = hub["region_id"]
        npc.append(
            {
                "id": f"region:{region_id}",
                "slug": slug,
                "kind": "region",
                "region_id": region_id,
                "name": f"{hub['region_name']} (all NPC stations)",
                "station_id": None,
            }
        )
        for station_id, station_name in hub["stations"]:
            npc.append(
                {
                    "id": f"station:{station_id}",
                    "slug": slug,
                    "kind": "station",
                    "region_id": region_id,
                    "name": station_name,
                    "station_id": station_id,
                }
            )

    structures = (
        await session.scalars(
            select(AuthedStructure)
            .where(AuthedStructure.has_market.is_(True))
            .order_by(AuthedStructure.structure_name)
        )
    ).all()

    shared: list[dict] = []
    for s in structures:
        owner_name = None
        token_linked = False
        if s.owner_character_id:
            user = await session.scalar(
                select(SsoUser).where(SsoUser.character_id == s.owner_character_id)
            )
            if user:
                owner_name = user.character_name
                token_linked = bool(user.refresh_token_enc)
        shared.append(
            {
                "id": f"structure:{s.structure_id}",
                "kind": "structure",
                "structure_id": s.structure_id,
                "name": s.structure_name,
                "system_name": s.system_name,
                "owner_character_id": s.owner_character_id,
                "owner_character_name": owner_name,
                "esi_linked": token_linked,
            }
        )

    return {"npc_hubs": npc, "shared_structures": shared}


async def _type_name(session: AsyncSession, type_id: int) -> str:
    row = await session.get(SdeTypeIndex, type_id)
    return row.name if row else str(type_id)


async def fetch_market_orders(
    session: AsyncSession,
    *,
    location_kind: str,
    location_id: int,
    type_id: int,
    order_type: str = "all",
    region_id: int | None = None,
) -> dict[str, Any]:
    if type_id <= 0:
        return {"error": "type_required", "message": "Select an item to view market orders."}

    type_name = await _type_name(session, type_id)
    buy_orders: list[dict] = []
    sell_orders: list[dict] = []

    if location_kind != "structure":
        hub = _hub_for_region(region_id) if region_id else None
        if location_kind == "station":
            loc_label = await _station_name(location_id)
        elif location_kind == "all_stations":
            loc_label = "All trade hubs (all stations)"
        else:
            loc_label = hub["region_name"] if hub else f"Region {region_id or location_id}"
        a4e = await _fetch_npc_orders_a4e(
            type_id=type_id,
            location_kind=location_kind,
            location_id=location_id,
            region_id=region_id,
            location_label=loc_label,
        )
        if a4e is not None:
            return _orders_response(
                location_kind=location_kind,
                location_id=location_id,
                location_label=a4e["location_label"],
                type_id=type_id,
                type_name=type_name,
                buy_orders=a4e["buy_orders"],
                sell_orders=a4e["sell_orders"],
                region_id=a4e.get("region_id"),
                data_source=a4e.get("data_source"),
                data_note=a4e.get("data_note"),
            )

    if location_kind == "all_stations":
        seen_regions: set[int] = set()
        for hub in NPC_MARKET_HUBS.values():
            rid = int(hub["region_id"])
            if rid in seen_regions:
                continue
            seen_regions.add(rid)
            rows = await esi_get_paged_list(
                f"/markets/{rid}/orders/",
                params={"type_id": type_id},
                max_pages=10,
            )
            for raw in rows:
                if not isinstance(raw, dict):
                    continue
                loc_id = int(raw.get("location_id") or 0)
                if loc_id not in ALL_NPC_STATION_IDS:
                    continue
                loc_label = await _station_name(loc_id)
                order = _normalize_order(raw, location_label=loc_label)
                if order["is_buy_order"]:
                    buy_orders.append(order)
                else:
                    sell_orders.append(order)

        buy_orders.sort(key=lambda o: o["price"], reverse=True)
        sell_orders.sort(key=lambda o: o["price"])
        return _orders_response(
            location_kind=location_kind,
            location_id=location_id,
            location_label="All trade hubs (all stations)",
            type_id=type_id,
            type_name=type_name,
            buy_orders=buy_orders,
            sell_orders=sell_orders,
            region_id=None,
        )

    if location_kind == "structure":
        character_id = await _structure_owner(session, location_id)
        status, probe = await esi_get(
            f"/markets/structures/{location_id}/",
            params={"page": 1},
            auth=True,
            session=session,
            character_id=character_id,
        )
        if status in (401, 403):
            character_id = await resolve_structure_market_character(session, location_id)
            if character_id:
                status, probe = await esi_get(
                    f"/markets/structures/{location_id}/",
                    params={"page": 1},
                    auth=True,
                    session=session,
                    character_id=character_id,
                )
        if status in (401, 403):
            cached = await _fetch_cached_structure_orders(
                session, location_id=location_id, type_id=type_id
            )
            if cached is not None:
                return cached
            return {
                "error": "esi_forbidden",
                "message": "Structure market requires a linked ESI token with structure market scope.",
                "status": status,
            }
        if status != 200:
            cached = await _fetch_cached_structure_orders(
                session, location_id=location_id, type_id=type_id
            )
            if cached is not None:
                return cached
            return {"error": "esi_error", "message": f"ESI returned {status}", "status": status}

        if not character_id:
            character_id = await resolve_structure_market_character(session, location_id)

        rows = await esi_get_paged_list(
            f"/markets/structures/{location_id}/",
            auth=True,
            session=session,
            character_id=character_id,
            max_pages=30,
        )
        struct = await session.scalar(
            select(AuthedStructure).where(AuthedStructure.structure_id == location_id)
        )
        label = struct.structure_name if struct else f"Structure {location_id}"
        for raw in rows:
            if not isinstance(raw, dict) or int(raw.get("type_id") or 0) != type_id:
                continue
            order = _normalize_order(raw, location_label=label)
            if order["is_buy_order"]:
                buy_orders.append(order)
            else:
                sell_orders.append(order)

        return _orders_response(
            location_kind=location_kind,
            location_id=location_id,
            location_label=label,
            type_id=type_id,
            type_name=type_name,
            buy_orders=buy_orders,
            sell_orders=sell_orders,
            region_id=region_id,
        )

    rid = region_id or location_id
    if location_kind == "station":
        rid = region_id or _region_for_station(location_id)
        if not rid:
            return {"error": "unknown_station", "message": "Station region not mapped."}

    params: dict[str, Any] = {"type_id": type_id}
    if order_type in ("buy", "sell"):
        params["order_type"] = order_type

    rows = await esi_get_paged_list(f"/markets/{rid}/orders/", params=params, max_pages=15)
    station_filter = location_id if location_kind == "station" else None

    for raw in rows:
        if not isinstance(raw, dict):
            continue
        loc_id = int(raw.get("location_id") or 0)
        if station_filter and loc_id != station_filter:
            continue
        loc_label = await _station_name(loc_id)
        order = _normalize_order(raw, location_label=loc_label)
        if order["is_buy_order"]:
            buy_orders.append(order)
        else:
            sell_orders.append(order)

    hub = _hub_for_region(rid)
    if location_kind == "station":
        loc_label = await _station_name(location_id)
    else:
        loc_label = hub["region_name"] if hub else f"Region {rid}"

    buy_orders.sort(key=lambda o: o["price"], reverse=True)
    sell_orders.sort(key=lambda o: o["price"])

    return _orders_response(
        location_kind=location_kind,
        location_id=location_id,
        location_label=loc_label,
        type_id=type_id,
        type_name=type_name,
        buy_orders=buy_orders,
        sell_orders=sell_orders,
        region_id=rid,
    )


def _orders_response(
    *,
    location_kind: str,
    location_id: int,
    location_label: str,
    type_id: int,
    type_name: str,
    buy_orders: list[dict],
    sell_orders: list[dict],
    region_id: int | None,
    data_source: str | None = None,
    data_note: str | None = None,
) -> dict[str, Any]:
    best_buy = max((o["price"] for o in buy_orders), default=None)
    best_sell = min((o["price"] for o in sell_orders), default=None) if sell_orders else None
    out: dict[str, Any] = {
        "location_kind": location_kind,
        "location_id": location_id,
        "location_label": location_label,
        "region_id": region_id,
        "type_id": type_id,
        "type_name": type_name,
        "buy_orders": buy_orders,
        "sell_orders": sell_orders,
        "summary": {
            "buy_count": len(buy_orders),
            "sell_count": len(sell_orders),
            "best_buy": best_buy,
            "best_sell": best_sell,
            "spread": (best_sell - best_buy) if best_buy is not None and best_sell is not None else None,
        },
    }
    if data_source:
        out["data_source"] = data_source
    if data_note:
        out["data_note"] = data_note
    return out


async def _structure_owner(session: AsyncSession, structure_id: int) -> int | None:
    row = await session.scalar(
        select(AuthedStructure).where(AuthedStructure.structure_id == structure_id)
    )
    if row and row.owner_character_id:
        return int(row.owner_character_id)
    return None


async def _fetch_cached_structure_orders(
    session: AsyncSession,
    *,
    location_id: int,
    type_id: int,
) -> dict[str, Any] | None:
    """Read structure orders from market-api Postgres cache (ESI structure sync)."""
    base = (settings.market_api_internal_url or "").strip().rstrip("/")
    if not base:
        return None

    struct = await session.scalar(
        select(AuthedStructure).where(AuthedStructure.structure_id == location_id)
    )
    label = struct.structure_name if struct else f"Structure {location_id}"
    if not struct and location_id == int(settings.wompstar_structure_id or 0):
        label = settings.wompstar_structure_name or label

    url = f"{base}/api/market/v1/browser/item/{type_id}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, params={"location_id": location_id})
        if resp.status_code != 200:
            return None
        body = resp.json()
    except Exception:
        logger.debug("market-api structure fallback failed", exc_info=True)
        return None

    if not isinstance(body, dict):
        return None

    type_name = str(body.get("type_name") or await _type_name(session, type_id))
    buy_orders: list[dict] = []
    sell_orders: list[dict] = []

    for raw in body.get("buy_orders") or []:
        if not isinstance(raw, dict):
            continue
        buy_orders.append(
            _normalize_order(
                {
                    **raw,
                    "type_id": type_id,
                    "location_id": location_id,
                    "is_buy_order": True,
                    "source": "market-api-cache",
                },
                location_label=label,
            )
        )
    for raw in body.get("sell_orders") or []:
        if not isinstance(raw, dict):
            continue
        sell_orders.append(
            _normalize_order(
                {
                    **raw,
                    "type_id": type_id,
                    "location_id": location_id,
                    "is_buy_order": False,
                    "source": "market-api-cache",
                },
                location_label=label,
            )
        )

    return _orders_response(
        location_kind="structure",
        location_id=location_id,
        location_label=label,
        type_id=type_id,
        type_name=type_name,
        buy_orders=buy_orders,
        sell_orders=sell_orders,
        region_id=None,
        data_source="market-api-cache",
        data_note="Cached structure orders (refreshed by market-api structure sync).",
    )


def _region_for_station(station_id: int) -> int | None:
    for hub in NPC_MARKET_HUBS.values():
        for sid, _ in hub["stations"]:
            if sid == station_id:
                return int(hub["region_id"])
    return None


def _hub_for_region(region_id: int) -> dict[str, Any] | None:
    for hub in NPC_MARKET_HUBS.values():
        if hub["region_id"] == region_id:
            return hub
    return None


async def _fetch_esi_history(*, region_id: int, type_id: int) -> list[dict]:
    status, body = await esi_get(f"/markets/{region_id}/history/", params={"type_id": type_id})
    if status != 200 or not isinstance(body, list):
        return []
    return [r for r in body if isinstance(r, dict)]


async def sync_market_history(
    session: AsyncSession,
    *,
    region_id: int,
    type_id: int,
    max_days: int = MARKET_HISTORY_CACHE_DAYS,
) -> int:
    start_day = date.today() - timedelta(days=max_days)
    if a4e_enabled():
        rows_raw = await fetch_region_history(
            type_id,
            region_id=region_id,
            start=start_day,
        )
        mapped: list[dict] = []
        for raw in rows_raw:
            day_row = history_row_to_day(raw)
            if day_row:
                mapped.append(day_row)
        if not mapped:
            return 0
        await session.execute(
            delete(MarketHistoryDay).where(
                MarketHistoryDay.type_id == type_id,
                MarketHistoryDay.region_id == region_id,
            )
        )
        batch: list[MarketHistoryDay] = []
        for r in mapped:
            try:
                day = date.fromisoformat(str(r["day"])[:10])
            except ValueError:
                continue
            batch.append(
                MarketHistoryDay(
                    type_id=type_id,
                    region_id=region_id,
                    day=day,
                    average=float(r.get("average") or 0),
                    highest=float(r.get("highest") or 0),
                    lowest=float(r.get("lowest") or 0),
                    volume=int(r.get("volume") or 0),
                    order_count=int(r.get("order_count") or 0),
                )
            )
        if batch:
            session.add_all(batch)
            await session.flush()
        return len(batch)

    rows_raw = await _fetch_esi_history(region_id=region_id, type_id=type_id)
    if not rows_raw:
        return 0

    await session.execute(
        delete(MarketHistoryDay).where(
            MarketHistoryDay.type_id == type_id,
            MarketHistoryDay.region_id == region_id,
        )
    )

    batch: list[MarketHistoryDay] = []
    for r in rows_raw:
        raw_day = r.get("date")
        if not raw_day:
            continue
        try:
            day = date.fromisoformat(str(raw_day)[:10])
        except ValueError:
            continue
        batch.append(
            MarketHistoryDay(
                type_id=type_id,
                region_id=region_id,
                day=day,
                average=float(r.get("average") or 0),
                highest=float(r.get("highest") or 0),
                lowest=float(r.get("lowest") or 0),
                volume=int(r.get("volume") or 0),
                order_count=int(r.get("order_count") or 0),
            )
        )
    if batch:
        session.add_all(batch)
        await session.flush()
    return len(batch)


def _history_needs_sync(cached: list[MarketHistoryDay], *, cutoff: date) -> bool:
    if len(cached) < MARKET_HISTORY_MIN_ROWS:
        return True
    latest = max(row.day for row in cached)
    if latest < date.today() - timedelta(days=MARKET_HISTORY_STALE_DAYS):
        return True
    earliest = min(row.day for row in cached)
    if earliest > cutoff + timedelta(days=7):
        return True
    return False


async def warm_type_market_history(
    session: AsyncSession,
    *,
    type_id: int,
    max_days: int = MARKET_HISTORY_CACHE_DAYS,
) -> dict[str, Any]:
    """Prefetch regional history for trade hubs when users browse SDE / market."""
    cutoff = date.today() - timedelta(days=max_days)
    regions_synced = 0
    rows_written = 0
    for hub in NPC_MARKET_HUBS.values():
        region_id = int(hub["region_id"])
        cached_rows = (
            await session.scalars(
                select(MarketHistoryDay)
                .where(
                    MarketHistoryDay.type_id == type_id,
                    MarketHistoryDay.region_id == region_id,
                    MarketHistoryDay.day >= cutoff,
                )
                .order_by(MarketHistoryDay.day)
            )
        ).all()
        if not _history_needs_sync(cached_rows, cutoff=cutoff):
            continue
        written = await sync_market_history(
            session,
            region_id=region_id,
            type_id=type_id,
            max_days=max_days,
        )
        if written:
            regions_synced += 1
            rows_written += written
    return {
        "type_id": type_id,
        "max_days": max_days,
        "regions_synced": regions_synced,
        "rows_written": rows_written,
    }


async def fetch_market_history(
    session: AsyncSession,
    *,
    region_id: int,
    type_id: int,
    max_days: int = MARKET_HISTORY_CACHE_DAYS,
) -> dict[str, Any]:
    cutoff = date.today() - timedelta(days=max_days)
    cached = (
        await session.scalars(
            select(MarketHistoryDay)
            .where(
                MarketHistoryDay.type_id == type_id,
                MarketHistoryDay.region_id == region_id,
                MarketHistoryDay.day >= cutoff,
            )
            .order_by(MarketHistoryDay.day)
        )
    ).all()

    if _history_needs_sync(cached, cutoff=cutoff):
        await sync_market_history(
            session,
            region_id=region_id,
            type_id=type_id,
            max_days=max_days,
        )
        cached = (
            await session.scalars(
                select(MarketHistoryDay)
                .where(
                    MarketHistoryDay.type_id == type_id,
                    MarketHistoryDay.region_id == region_id,
                    MarketHistoryDay.day >= cutoff,
                )
                .order_by(MarketHistoryDay.day)
            )
        ).all()

    type_name = await _type_name(session, type_id)
    hub = _hub_for_region(region_id)
    return {
        "region_id": region_id,
        "region_name": hub["region_name"] if hub else str(region_id),
        "type_id": type_id,
        "type_name": type_name,
        "max_days": max_days,
        "days": [
            {
                "day": h.day.isoformat(),
                "average": h.average,
                "highest": h.highest,
                "lowest": h.lowest,
                "volume": h.volume,
                "order_count": h.order_count,
            }
            for h in cached
        ],
        "source": "adam4eve" if a4e_enabled() else "esi",
        "note": (
            "Regional NPC market history via Adam4EVE (orderbook-derived)."
            if a4e_enabled()
            else "Regional NPC market history from ESI. Structure-specific history is not published."
        ),
        "synced_at": datetime.now(UTC).isoformat(),
    }
