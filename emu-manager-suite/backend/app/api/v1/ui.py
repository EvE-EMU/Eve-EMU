"""UI customization — desktop backgrounds (auth-gated admin writes)."""

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_api_key
from app.config import settings
from app.db.session import get_db
from app.models import DesktopBackground
from app.schemas import (
    DesktopBackgroundCreate,
    DesktopBackgroundOut,
    DesktopBackgroundUpdate,
)
from app.services.media_storage import delete_background_file, save_background_video

router = APIRouter(prefix="/ui/desktop-backgrounds", tags=["UI"])


async def _deactivate_other_backgrounds(db: AsyncSession, keep_id: int) -> None:
    await db.execute(
        update(DesktopBackground)
        .where(DesktopBackground.id != keep_id)
        .values(active=False)
    )


def _require_admin_key(x_emums_key: str | None = Header(default=None, alias="X-EMUMS-Key")) -> None:
    if not x_emums_key or x_emums_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-EMUMS-Key header",
        )


@router.get("", response_model=list[DesktopBackgroundOut])
async def list_desktop_backgrounds(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    x_emums_key: str | None = Header(default=None, alias="X-EMUMS-Key"),
) -> list[DesktopBackground]:
    if not active_only:
        _require_admin_key(x_emums_key)

    stmt = select(DesktopBackground).order_by(DesktopBackground.sort_order, DesktopBackground.id)
    if active_only:
        stmt = stmt.where(DesktopBackground.active.is_(True))

    rows = await db.scalars(stmt)
    return list(rows.all())


@router.post(
    "/upload",
    response_model=DesktopBackgroundOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def upload_desktop_background(
    label: str = Form(..., min_length=1, max_length=128),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> DesktopBackground:
    _filename, video_url = await save_background_video(file, label)
    max_sort = await db.scalar(select(func.max(DesktopBackground.sort_order)))
    row = DesktopBackground(
        label=label.strip(),
        video_url=video_url,
        active=True,
        sort_order=int(max_sort or -1) + 1,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    await _deactivate_other_backgrounds(db, row.id)
    await db.flush()
    await db.commit()
    return row


@router.post(
    "",
    response_model=DesktopBackgroundOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def create_desktop_background(
    payload: DesktopBackgroundCreate, db: AsyncSession = Depends(get_db)
) -> DesktopBackground:
    row = DesktopBackground(**payload.model_dump())
    db.add(row)
    await db.flush()
    await db.refresh(row)
    if row.active:
        await _deactivate_other_backgrounds(db, row.id)
        await db.flush()
    await db.commit()
    return row


@router.patch(
    "/{background_id}",
    response_model=DesktopBackgroundOut,
    dependencies=[Depends(require_api_key)],
)
async def update_desktop_background(
    background_id: int,
    payload: DesktopBackgroundUpdate,
    db: AsyncSession = Depends(get_db),
) -> DesktopBackground:
    row = await db.get(DesktopBackground, background_id)
    if not row:
        raise HTTPException(status_code=404, detail="Background not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(row, field, value)
    if data.get("active") is True:
        await _deactivate_other_backgrounds(db, background_id)
    await db.flush()
    await db.commit()
    await db.refresh(row)
    return row


@router.delete(
    "/{background_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
async def delete_desktop_background(
    background_id: int, db: AsyncSession = Depends(get_db)
) -> None:
    row = await db.get(DesktopBackground, background_id)
    if not row:
        raise HTTPException(status_code=404, detail="Background not found")
    delete_background_file(row.video_url)
    await db.delete(row)
    await db.flush()
    await db.commit()
