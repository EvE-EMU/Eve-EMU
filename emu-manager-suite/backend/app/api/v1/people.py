"""Onboarding, admission ranking, standings, and calendar."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_administrator, require_api_key
from app.db.session import get_db
from app.services.rbac import UserAuthContext

router = APIRouter(
    prefix="/people",
    tags=["People"],
    dependencies=[Depends(require_api_key)],
)



class CompleteTaskBody(BaseModel):
    task_slug: str


class AdmissionConfigBody(BaseModel):
    admit_threshold: float | None = None
    review_threshold: float | None = None
    kpi_updates: list[dict] = Field(default_factory=list)


@router.get("/onboarding")
async def get_onboarding(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    from app.services.onboarding import onboarding_status

    status = await onboarding_status(
        db, character_id=auth.character_id, character_name=auth.character_name
    )
    await db.commit()
    return status


@router.post("/onboarding/complete")
async def complete_task(
    body: CompleteTaskBody,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    from app.services.onboarding import complete_onboarding_task

    result = await complete_onboarding_task(
        db,
        character_id=auth.character_id,
        character_name=auth.character_name,
        task_slug=body.task_slug,
    )
    if result.get("error"):
        raise HTTPException(400, detail=result["error"])
    await db.commit()
    return result


@router.get("/admission/rank")
async def admission_rank_me(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    from app.services.onboarding import admission_rank

    result = await admission_rank(
        db, character_id=auth.character_id, character_name=auth.character_name
    )
    await db.commit()
    return result


@router.get("/admission/rank/{character_id}")
async def admission_rank_character(
    character_id: int,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(require_administrator),
) -> dict:
    from app.services.onboarding import admission_rank
    from app.models.tools import SsoUser
    from sqlalchemy import select

    user = await db.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    result = await admission_rank(
        db,
        character_id=character_id,
        character_name=(user.character_name if user else ""),
    )
    await db.commit()
    return result


@router.get("/admission/config")
async def admission_config(
    db: AsyncSession = Depends(get_db),
    _auth: UserAuthContext = Depends(require_administrator),
) -> dict:
    from app.services.onboarding import list_admission_kpis

    return await list_admission_kpis(db)


@router.patch("/admission/config")
async def patch_admission_config(
    body: AdmissionConfigBody,
    db: AsyncSession = Depends(get_db),
    _auth: UserAuthContext = Depends(require_administrator),
) -> dict:
    from app.services.onboarding import update_admission_config

    result = await update_admission_config(
        db,
        admit_threshold=body.admit_threshold,
        review_threshold=body.review_threshold,
        kpi_updates=body.kpi_updates,
    )
    await db.commit()
    return result


@router.post("/standings/sync")
async def sync_standings(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    from app.services.standings_sync import sync_character_standings

    result = await sync_character_standings(db, auth.character_id)
    if result.get("error") and result.get("count", 0) == 0:
        raise HTTPException(400, detail=result.get("message") or result["error"])
    await db.commit()
    return result


@router.get("/standings")
async def get_standings(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    from app.services.standings_sync import standings_board

    return await standings_board(db, auth.character_id)


@router.get("/calendar")
async def get_calendar(
    month: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    from app.services.calendar_board import calendar_events

    return await calendar_events(db, character_id=auth.character_id, month=month)


@router.get("/permissions/catalog")
async def permissions_catalog() -> dict:
    """All known permission strings for the permissions manager UI."""
    from app.services.rbac import MODULE_PERMISSIONS

    all_perms: set[str] = set()
    for perms in MODULE_PERMISSIONS.values():
        all_perms.update(perms)
    all_perms.update(
        {
            "admin",
            "director",
            "settings.admin",
            "audit.view",
            "hr.manage",
            "storefront.admin",
            "admission.review",
        }
    )
    return {
        "modules": [
            {"id": level, "permissions": perms} for level, perms in MODULE_PERMISSIONS.items()
        ],
        "all_permissions": sorted(all_perms),
    }
