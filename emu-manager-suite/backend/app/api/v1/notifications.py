"""In-app notification feed — extensible per plugin/type."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_api_key
from app.db.session import get_db
from app.models import NotificationRead, SystemNotification
from app.schemas import NotificationCreate, NotificationMarkReadIn, NotificationOut
from app.services.character_roster import roster_character_ids
from app.services.rbac import UserAuthContext

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _notification_visible(recipient_id: int | None, roster_ids: set[int]) -> bool:
    if recipient_id is None:
        return True
    return int(recipient_id) in roster_ids


async def _read_ids_for_character(db: AsyncSession, character_id: int) -> set[int]:
    rows = await db.scalars(
        select(NotificationRead.notification_id).where(
            NotificationRead.character_id == character_id
        )
    )
    return {int(r) for r in rows.all()}


def _serialize(row: SystemNotification, *, read: bool) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        plugin=row.plugin,
        type=row.type,
        title=row.title,
        body=row.body,
        payload_json=row.payload_json,
        recipient_character_id=row.recipient_character_id,
        read=read,
        created_at=row.created_at,
    )


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
    unread_only: bool = False,
    since_id: int | None = None,
    limit: int = Query(50, le=200),
) -> list[NotificationOut]:
    roster = await roster_character_ids(db, auth.character_id)
    read_for_viewer = await _read_ids_for_character(db, auth.character_id)

    stmt = select(SystemNotification).order_by(SystemNotification.created_at.desc()).limit(limit * 3)
    if since_id:
        stmt = stmt.where(SystemNotification.id > since_id)
    rows = (await db.scalars(stmt)).all()

    out: list[NotificationOut] = []
    for row in rows:
        if not _notification_visible(row.recipient_character_id, roster):
            continue
        is_read = row.read if row.recipient_character_id is None else row.id in read_for_viewer
        if unread_only and is_read:
            continue
        out.append(_serialize(row, read=is_read))
        if len(out) >= limit:
            break
    return out


@router.get("/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict[str, int]:
    roster = await roster_character_ids(db, auth.character_id)
    read_for_viewer = await _read_ids_for_character(db, auth.character_id)
    rows = (await db.scalars(select(SystemNotification))).all()
    count = 0
    for row in rows:
        if not _notification_visible(row.recipient_character_id, roster):
            continue
        is_read = row.read if row.recipient_character_id is None else row.id in read_for_viewer
        if not is_read:
            count += 1
    return {"count": count}


@router.post(
    "",
    response_model=NotificationOut,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
async def create_notification(
    payload: NotificationCreate, db: AsyncSession = Depends(get_db)
) -> NotificationOut:
    row = SystemNotification(**payload.model_dump())
    db.add(row)
    await db.flush()
    await db.refresh(row)
    await db.commit()
    return _serialize(row, read=row.read)


@router.patch("/read")
async def mark_notifications_read(
    payload: NotificationMarkReadIn,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict[str, int]:
    roster = await roster_character_ids(db, auth.character_id)
    updated = 0

    if payload.all:
        rows = (await db.scalars(select(SystemNotification))).all()
        for row in rows:
            if not _notification_visible(row.recipient_character_id, roster):
                continue
            if row.recipient_character_id is None:
                if not row.read:
                    row.read = True
                    updated += 1
            else:
                existing = await db.scalar(
                    select(NotificationRead).where(
                        NotificationRead.notification_id == row.id,
                        NotificationRead.character_id == auth.character_id,
                    )
                )
                if not existing:
                    db.add(
                        NotificationRead(
                            notification_id=row.id,
                            character_id=auth.character_id,
                        )
                    )
                    updated += 1
        await db.commit()
        return {"updated": updated}

    if not payload.ids:
        raise HTTPException(status_code=400, detail="Provide ids or all=true")

    for nid in payload.ids:
        row = await db.get(SystemNotification, nid)
        if not row or not _notification_visible(row.recipient_character_id, roster):
            continue
        if row.recipient_character_id is None:
            if not row.read:
                row.read = True
                updated += 1
        else:
            existing = await db.scalar(
                select(NotificationRead).where(
                    NotificationRead.notification_id == row.id,
                    NotificationRead.character_id == auth.character_id,
                )
            )
            if not existing:
                db.add(
                    NotificationRead(
                        notification_id=row.id,
                        character_id=auth.character_id,
                    )
                )
                updated += 1
    await db.commit()
    return {"updated": updated}
