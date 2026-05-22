from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services.appraisal import run_appraisal
from app.services.janice import JANICE_MARKETS, janice_configured, janice_validate_key

router = APIRouter()


class AppraisalRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=200_000)
    sell_market: str = "jita"
    buy_market: str | None = None
    location_id: int | None = None


@router.get("/meta")
async def appraisal_meta() -> dict:
    return {
        "janice_configured": janice_configured(),
        "janice_ok": await janice_validate_key() if janice_configured() else False,
        "markets": [
            {"id": key, "label": label, "janice_id": mid}
            for key, (mid, label) in JANICE_MARKETS.items()
        ],
        "destination": {
            "structure_id": settings.wompstar_structure_id,
            "name": settings.wompstar_structure_name,
        },
        "buyback_url": settings.buyback_public_url,
    }


@router.post("")
async def appraise_items(body: AppraisalRequest) -> dict:
    loc = body.location_id or settings.wompstar_structure_id
    if not loc:
        raise HTTPException(503, "WOMPSTAR structure not configured")
    if not janice_configured():
        raise HTTPException(
            503,
            "Janice API key not configured (MARKET_JANICE_API_KEY or BUYBACKPROGRAM_PRICE_JANICE_API_KEY)",
        )
    return await run_appraisal(
        text=body.text,
        sell_market=body.sell_market,
        buy_market=body.buy_market,
        location_id=int(loc),
    )
