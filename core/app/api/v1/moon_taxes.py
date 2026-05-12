"""Moon mining tax plugin (Discord bot calls core; core calls ESI with linked character tokens)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.v1.bot_secret import require_discord_bot_secret
from app.config import settings
from app.services.moon_taxes_compute import compute_moon_tax_summary, summary_to_dict

router = APIRouter(prefix="/plugins/moon-taxes", tags=["Moon taxes"])


class MoonTaxSummaryIn(BaseModel):
    discord_user_id: int = Field(..., ge=1)
    character_id: int | None = Field(None, description="Linked character id; default is core main")
    period_days: int = Field(30, ge=1, le=90)
    include_assets: bool = Field(
        False,
        description="If true, also pulls character assets (requires esi-assets.read_assets.v1 on the token).",
    )


@router.post("/summary")
async def moon_tax_summary(
    body: MoonTaxSummaryIn,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any] | JSONResponse:
    """Compare mining ledger vs item_exchange contracts to ``CORE_MOON_TAX_ASSIGNEE_ID``; estimate un-contracted value."""
    require_discord_bot_secret(authorization)
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="CORE_DATABASE_URL is not set.")

    s = await compute_moon_tax_summary(
        discord_user_id=body.discord_user_id,
        character_id=body.character_id,
        period_days=body.period_days,
        include_assets=body.include_assets,
    )
    payload = summary_to_dict(s)
    if not s.ok:
        return JSONResponse(status_code=422, content=payload)
    return payload
