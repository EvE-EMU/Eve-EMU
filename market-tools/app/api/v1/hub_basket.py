from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.hub_basket import (
    TRADE_HUB_REGIONS,
    format_hub_basket_report,
    run_hub_basket_compare,
)

router = APIRouter()


class HubBasketRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=200_000)
    hubs: list[str] | None = Field(
        default=None,
        description="Subset of jita, amarr, dodixie, rens, hek (default: all five)",
    )
    max_pages: int = Field(default=8, ge=1, le=50)
    concurrency: int = Field(default=6, ge=1, le=20)


@router.get("/meta")
async def hub_basket_meta() -> dict:
    return {
        "hubs": [
            {"id": key, "region_id": rid, "label": label}
            for key, (rid, label) in TRADE_HUB_REGIONS.items()
        ],
        "paste_formats": [
            "Item Name x1234",
            "1234 x Item Name",
            "Item Name<TAB>1234",
        ],
        "method": "esi_sell_order_walk",
    }


@router.post("")
async def hub_basket_compare(body: HubBasketRequest) -> dict:
    """Compare full-quantity buy cost across trade hubs (live ESI sell orders)."""
    result = await run_hub_basket_compare(
        body.text,
        hubs=body.hubs,
        max_pages=body.max_pages,
        concurrency=body.concurrency,
    )
    result["report"] = format_hub_basket_report(result)
    return result
