"""Finance plugin: market browse (NPC region orders + player structures with verified tokens)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.api.v1.bot_secret import require_discord_bot_secret
from app.config import settings
from app.services.finance_market import (
    finance_contribute_structures,
    finance_list_structures,
    finance_search_types,
    finance_top_sells,
)

router = APIRouter(prefix="/plugins/finance", tags=["Finance"])


class FinanceContributeIn(BaseModel):
    discord_user_id: int = Field(..., ge=1)
    structure_ids: list[int] = Field(..., min_length=1, max_length=10)

    @field_validator("structure_ids")
    @classmethod
    def positive_structure_ids(cls, v: list[int]) -> list[int]:
        for x in v:
            if int(x) <= 0:
                raise ValueError("structure_ids must be positive integers")
        return v


@router.get("/types")
async def finance_types(
    authorization: Annotated[str | None, Header()] = None,
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(15, ge=1, le=50),
) -> list[dict[str, Any]]:
    require_discord_bot_secret(authorization)
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="CORE_DATABASE_URL is not set.")
    return await finance_search_types(q=q, limit=limit)


@router.get("/structures")
async def finance_structures(authorization: Annotated[str | None, Header()] = None) -> list[dict[str, Any]]:
    require_discord_bot_secret(authorization)
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="CORE_DATABASE_URL is not set.")
    return await finance_list_structures()


@router.post("/structures/contribute")
async def finance_structures_contribute(
    body: FinanceContributeIn,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    require_discord_bot_secret(authorization)
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="CORE_DATABASE_URL is not set.")
    return await finance_contribute_structures(
        discord_user_id=body.discord_user_id,
        structure_ids=body.structure_ids,
    )


@router.get("/sells")
async def finance_sells(
    authorization: Annotated[str | None, Header()] = None,
    type_id: int = Query(..., ge=1),
    region_id: int | None = Query(None, ge=1),
    limit: int | None = Query(None, ge=1),
) -> dict[str, Any]:
    require_discord_bot_secret(authorization)
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="CORE_DATABASE_URL is not set.")
    lim = int(limit) if limit is not None else int(settings.finance_sells_default_limit or 15)
    out = await finance_top_sells(type_id=type_id, region_id=region_id, limit=lim)
    if not out.get("ok"):
        raise HTTPException(status_code=422, detail=str(out.get("error") or "finance_error"))
    return out
