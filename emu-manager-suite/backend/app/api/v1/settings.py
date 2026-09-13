"""Org settings CRUD."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_administrator, require_api_key
from app.db.session import get_db
from app.models import OrgSettings
from app.schemas import OrgSettingsOut, OrgSettingsUpdate
from app.services.rbac import UserAuthContext

router = APIRouter(prefix="/settings", tags=["Settings"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=OrgSettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)) -> OrgSettings:
    row = await db.scalar(select(OrgSettings).limit(1))
    if not row:
        raise HTTPException(status_code=404, detail="Settings not initialized")
    return row


@router.patch("", response_model=OrgSettingsOut)
async def update_settings(
    payload: OrgSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: UserAuthContext = Depends(require_administrator),
) -> OrgSettings:
    row = await db.scalar(select(OrgSettings).limit(1))
    if not row:
        raise HTTPException(status_code=404, detail="Settings not initialized")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.flush()
    await db.commit()
    return row
