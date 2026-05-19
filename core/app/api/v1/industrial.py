"""Industrial Command plugin API (Discord bot or AA workers may call with bot secret)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header

from app.api.v1.bot_secret import require_discord_bot_secret
from app.services.industrial_planning import SplitMassBuildIn, split_mass_build

router = APIRouter(prefix="/plugins/industrial", tags=["Industrial"])


@router.post("/plan/split")
async def plan_split_mass_build(
    body: SplitMassBuildIn,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Split a mass build into sub-order rows (no persistence; AA ``industry_suite`` stores results)."""
    require_discord_bot_secret(authorization)
    plans = split_mass_build(body)
    return {
        "ok": True,
        "corporation_id": body.corporation_id,
        "sub_orders": [p.model_dump() for p in plans],
    }
