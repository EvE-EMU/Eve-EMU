"""Margin finder: buy/sell spread within a location (Adam4EVE-style)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.db.models import MarketOrder
from app.db.session import session_scope
from app.services.margin_stats import enrich_margin_stats
from app.services.name_resolver import attach_type_names


async def margin_rows(
    *,
    location_id: int,
    min_trades: int = 1,
    min_isk_volume: float = 0,
    limit: int = 100,
) -> list[dict]:
    """Best buy vs best sell per type at a structure."""
    async with session_scope() as session:
        buy_q = (
            select(
                MarketOrder.type_id,
                func.max(MarketOrder.price).label("buy_price"),
                func.count().label("buy_orders"),
                func.sum(MarketOrder.volume_remain).label("buy_vol"),
            )
            .where(MarketOrder.location_id == location_id, MarketOrder.is_buy.is_(True))
            .group_by(MarketOrder.type_id)
        )
        sell_q = (
            select(
                MarketOrder.type_id,
                func.min(MarketOrder.price).label("sell_price"),
                func.count().label("sell_orders"),
                func.sum(MarketOrder.volume_remain).label("sell_vol"),
            )
            .where(MarketOrder.location_id == location_id, MarketOrder.is_buy.is_(False))
            .group_by(MarketOrder.type_id)
        )
        buys = {r.type_id: r for r in (await session.execute(buy_q)).all()}
        sells = {r.type_id: r for r in (await session.execute(sell_q)).all()}

    out: list[dict] = []
    for type_id in sorted(set(buys) & set(sells)):
        b = buys[type_id]
        s = sells[type_id]
        buy_p = float(b.buy_price or 0)
        sell_p = float(s.sell_price or 0)
        if buy_p <= 0 or sell_p <= 0 or sell_p <= buy_p:
            continue
        spread = sell_p - buy_p
        isk = spread * min(float(b.buy_vol or 0), float(s.sell_vol or 0))
        trades = int(b.buy_orders or 0) + int(s.sell_orders or 0)
        if trades < min_trades or isk < min_isk_volume:
            continue
        out.append(
            {
                "type_id": type_id,
                "buy_price": buy_p,
                "sell_price": sell_p,
                "spread_isk": spread,
                "spread_pct": round(100 * spread / buy_p, 2),
                "spread_volume_isk": isk,
                "buy_orders": int(b.buy_orders or 0),
                "sell_orders": int(s.sell_orders or 0),
                "buy_volume": int(b.buy_vol or 0),
                "sell_volume": int(s.sell_vol or 0),
            }
        )
    out.sort(key=lambda x: x["spread_isk"], reverse=True)
    out = out[:limit]
    await attach_type_names(out, location_id=location_id)
    await enrich_margin_stats(out, location_id=location_id)
    return out
