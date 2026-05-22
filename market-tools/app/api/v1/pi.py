from fastapi import APIRouter, Query

from app.services.pi_rank import pi_rank_rows

router = APIRouter()


@router.get("/rank")
async def pi_rank(
    sale_hub: str = Query("jita", pattern="^(jita|amarr|wompstar)$"),
    buy_from: str = Query("sell_orders", pattern="^(sell_orders|buy_orders)$"),
    sell_to: str = Query("sell_orders", pattern="^(sell_orders|buy_orders)$"),
    mode: str = Query("factory", pattern="^(factory|extract|both)$"),
    tier: int | None = Query(None, ge=1, le=4),
    customs_pct: float = Query(10.0, ge=0, le=50),
    market_pct: float = Query(7.5, ge=0, le=50),
    limit: int = Query(200, ge=1, le=500),
) -> dict:
    """PI schematic profitability ranked by ISK per hour."""
    if mode == "both":
        factory = await pi_rank_rows(
            sale_hub=sale_hub,
            buy_from=buy_from,
            sell_to=sell_to,
            mode="factory",
            tier=tier,
            customs_pct=customs_pct,
            market_pct=market_pct,
            limit=limit,
        )
        extract = await pi_rank_rows(
            sale_hub=sale_hub,
            buy_from=buy_from,
            sell_to=sell_to,
            mode="extract",
            tier=tier,
            customs_pct=customs_pct,
            market_pct=market_pct,
            limit=limit,
        )
        return {
            **factory,
            "rows": factory["rows"] + extract["rows"],
            "mode": "both",
        }
    return await pi_rank_rows(
        sale_hub=sale_hub,
        buy_from=buy_from,
        sell_to=sell_to,
        mode=mode,
        tier=tier,
        customs_pct=customs_pct,
        market_pct=market_pct,
        limit=limit,
    )
