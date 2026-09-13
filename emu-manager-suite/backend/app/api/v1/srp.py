"""SRP submission and rate lookup."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.tools import SrpLoss
from app.services.character_roster import roster_character_ids
from app.services.rbac import UserAuthContext
from app.services.srp_service import analyze_killmail, list_eligible_losses, list_rate_rules, submit_srp_claim

router = APIRouter(prefix="/srp", tags=["SRP"])


class SrpSubmitIn(BaseModel):
    killmail_id: int = Field(..., gt=0)
    killmail_hash: str = Field(..., min_length=8, max_length=64)
    character_id: int = Field(..., gt=0)
    notes: str = Field(default="", max_length=2000)


def _require_srp_submit(auth: UserAuthContext) -> None:
    if not auth.has_permission("srp.submit"):
        raise HTTPException(403, detail="SRP submission requires member access.")


def _rate_out(rule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "label": rule.label,
        "ship_type_id": rule.ship_type_id,
        "ship_type_name": rule.ship_type_name,
        "doctrine_slug": rule.doctrine_slug,
        "base_srp_isk": str(rule.base_srp_isk),
        "max_percent": str(rule.max_percent) if rule.max_percent is not None else None,
        "doctrine_multiplier": str(rule.doctrine_multiplier),
        "meta_multiplier": str(rule.meta_multiplier),
        "shitfit_multiplier": str(rule.shitfit_multiplier),
        "allow_shitfit": rule.allow_shitfit,
        "enabled": rule.enabled,
        "priority": rule.priority,
    }


def _claim_out(row: SrpLoss) -> dict[str, Any]:
    return {
        "id": row.id,
        "killmail_id": row.killmail_id,
        "killmail_hash": row.killmail_hash,
        "character_id": row.character_id,
        "character_name": row.character_name,
        "ship_type_id": row.ship_type_id,
        "ship_type_name": row.ship_type_name,
        "total_value_isk": str(row.total_value_isk),
        "srp_amount_isk": str(row.srp_amount_isk),
        "fit_grade": row.fit_grade,
        "doctrine_slug": row.doctrine_slug,
        "doctrine_match_pct": row.doctrine_match_pct,
        "status": row.status,
        "zkill_url": row.zkill_url,
        "solar_system_name": row.solar_system_name,
        "killed_at": row.killed_at.isoformat() if row.killed_at else None,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "submitted_notes": row.submitted_notes,
    }


@router.get("/rates")
async def srp_rates(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rules = await list_rate_rules(db, enabled_only=True)
    return [_rate_out(r) for r in rules]


@router.get("/eligible-losses")
async def srp_eligible_losses(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    _require_srp_submit(auth)
    return await list_eligible_losses(db, viewer_character_id=auth.character_id)


@router.get("/preview")
async def srp_preview(
    killmail_id: int = Query(..., gt=0),
    killmail_hash: str = Query(..., min_length=8),
    character_id: int = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    _require_srp_submit(auth)
    allowed = await roster_character_ids(db, auth.character_id)
    if character_id not in allowed:
        raise HTTPException(403, detail="Character not in your roster.")
    return await analyze_killmail(
        db,
        killmail_id=killmail_id,
        killmail_hash=killmail_hash,
        character_id=character_id,
    )


@router.post("/submit")
async def srp_submit(
    body: SrpSubmitIn,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    _require_srp_submit(auth)
    result = await submit_srp_claim(
        db,
        viewer_character_id=auth.character_id,
        killmail_id=body.killmail_id,
        killmail_hash=body.killmail_hash,
        character_id=body.character_id,
        notes=body.notes,
    )
    if not result.get("ok"):
        raise HTTPException(400, detail=result.get("error") or "Submission failed.")
    return result


@router.get("/claims")
async def srp_my_claims(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    _require_srp_submit(auth)
    char_ids = await roster_character_ids(db, auth.character_id)
    rows = (
        await db.scalars(
            select(SrpLoss)
            .where(SrpLoss.character_id.in_(char_ids))
            .order_by(SrpLoss.submitted_at.desc(), SrpLoss.id.desc())
        )
    ).all()
    return [_claim_out(r) for r in rows]
