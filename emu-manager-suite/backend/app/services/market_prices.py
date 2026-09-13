"""Batch hub buy/sell prices for production planning — Janice preferred, ESI fallback."""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SdeTypeIndex
from app.services.janice import JANICE_MARKETS, janice_configured, janice_prices_by_type_id
from app.services.market_browser import fetch_market_orders

logger = logging.getLogger(__name__)

_price_cache: dict[tuple[str, int], tuple[float | None, float | None]] = {}


async def _esi_hub_prices(
    session: AsyncSession,
    type_ids: set[int],
    *,
    hub: str = "jita",
) -> dict[int, dict[str, float | None]]:
    from app.services.market_browser import NPC_MARKET_HUBS

    hub_cfg = NPC_MARKET_HUBS.get(hub) or NPC_MARKET_HUBS["jita"]
    region_id = int(hub_cfg["region_id"])
    out: dict[int, dict[str, float | None]] = {}

    missing = [tid for tid in type_ids if (hub, tid) not in _price_cache]
    for tid in missing:
        try:
            result = await fetch_market_orders(
                session,
                location_kind="region",
                location_id=region_id,
                type_id=tid,
                region_id=region_id,
            )
            summary = result.get("summary") if isinstance(result, dict) else {}
            buy = summary.get("best_buy") if isinstance(summary, dict) else None
            sell = summary.get("best_sell") if isinstance(summary, dict) else None
            _price_cache[(hub, tid)] = (
                float(buy) if buy is not None else None,
                float(sell) if sell is not None else None,
            )
        except Exception:
            logger.debug("esi price fetch failed for type %s", tid)
            _price_cache[(hub, tid)] = (None, None)

    fallback: dict[int, Decimal] = {}
    need_fallback = [tid for tid in type_ids if _price_cache.get((hub, tid)) == (None, None)]
    if need_fallback:
        rows = (
            await session.scalars(select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(need_fallback)))
        ).all()
        fallback = {int(r.type_id): Decimal(str(r.base_price or 0)) for r in rows}

    for tid in type_ids:
        buy, sell = _price_cache.get((hub, tid), (None, None))
        if buy is None and tid in fallback:
            buy = float(fallback[tid])
        if sell is None and tid in fallback:
            sell = float(fallback[tid]) * 1.05
        out[tid] = {"buy": buy, "sell": sell}
    return out


async def hub_prices_for_types(
    session: AsyncSession,
    type_ids: set[int],
    *,
    hub: str = "jita",
) -> tuple[dict[int, dict[str, float | None]], str]:
    """Return per-type buy/sell ISK and pricing source label."""
    if not type_ids:
        return {}, "none"

    hub_key = hub.lower()
    if janice_configured():
        janice_rows = await janice_prices_by_type_id(sorted(type_ids), market=hub_key)
        out: dict[int, dict[str, float | None]] = {}
        missing: set[int] = set()
        for tid in type_ids:
            row = janice_rows.get(tid)
            if row:
                out[tid] = {
                    "buy": row.get("buy"),
                    "sell": row.get("sell"),
                    "split": row.get("split"),
                }
            else:
                missing.add(tid)
        if missing:
            esi = await _esi_hub_prices(session, missing, hub=hub_key)
            out.update(esi)
        market_label = JANICE_MARKETS.get(hub_key, (0, hub_key))[1]
        return out, f"janice ({market_label})"

    out = await _esi_hub_prices(session, type_ids, hub=hub_key)
    return out, f"esi ({hub_key})"
