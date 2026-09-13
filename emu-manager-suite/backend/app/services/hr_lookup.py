"""HR pilot lookup — corp title roles configured in admin."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tools import AuditProfile, CharacterCorpTitle, HrRoleTitle, SsoUser
from app.services.rbac import UserAuthContext


async def viewer_has_hr_lookup(db: AsyncSession, auth: UserAuthContext) -> bool:
    if auth.has_permission("audit.view") or auth.has_permission("director"):
        return True
    if not auth.corporation_id:
        return False
    hr_titles = (
        await db.scalars(
            select(HrRoleTitle).where(
                HrRoleTitle.active.is_(True),
                HrRoleTitle.corporation_id == int(auth.corporation_id),
            )
        )
    ).all()
    if not hr_titles:
        return False
    hr_ids = {int(t.title_id) for t in hr_titles}
    char_titles = (
        await db.scalars(
            select(CharacterCorpTitle).where(CharacterCorpTitle.character_id == auth.character_id)
        )
    ).all()
    return any(int(ct.title_id) in hr_ids for ct in char_titles)


async def search_pilots(db: AsyncSession, query: str, *, limit: int = 25) -> list[dict]:
    q = query.strip()
    if len(q) < 2:
        return []
    pattern = f"%{q}%"
    profiles = (
        await db.scalars(
            select(AuditProfile)
            .where(AuditProfile.character_name.ilike(pattern))
            .order_by(AuditProfile.character_name)
            .limit(limit)
        )
    ).all()
    users = (
        await db.scalars(
            select(SsoUser)
            .where(SsoUser.character_name.ilike(pattern))
            .order_by(SsoUser.character_name)
            .limit(limit)
        )
    ).all()
    seen: set[int] = set()
    out: list[dict] = []
    for row in list(profiles) + list(users):
        cid = int(row.character_id)
        if cid in seen:
            continue
        seen.add(cid)
        name = row.character_name
        corp = getattr(row, "corporation_name", "") or ""
        out.append(
            {
                "character_id": cid,
                "character_name": name,
                "corporation_name": corp,
            }
        )
        if len(out) >= limit:
            break
    return out


async def lookup_pilot_by_id(db: AsyncSession, character_id: int) -> dict | None:
    profile = await db.scalar(
        select(AuditProfile).where(AuditProfile.character_id == character_id)
    )
    if profile:
        return {
            "character_id": int(profile.character_id),
            "character_name": profile.character_name,
            "corporation_name": profile.corporation_name,
            "last_sync_at": profile.last_sync_at.isoformat() if profile.last_sync_at else None,
        }
    user = await db.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    if user:
        return {
            "character_id": int(user.character_id),
            "character_name": user.character_name,
            "corporation_name": user.corporation_name,
            "last_sync_at": user.last_login_at.isoformat() if user.last_login_at else None,
        }
    return None
