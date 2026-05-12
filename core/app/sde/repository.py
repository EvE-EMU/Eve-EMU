"""Async SDE reads (Postgres)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.db.session import session_scope
from app.media.evetech import type_icon_url, type_render_url
from app.sde.models import SdeInvGroup, SdeMapSolarSystem, SdeType
from app.sde.schemas import (
    SdeInvGroupOut,
    SdeSolarSystemOut,
    SdeStatusOut,
    SdeTypeOut,
)


async def sde_status() -> SdeStatusOut:
    from app.config import settings

    if not settings.database_url:
        return SdeStatusOut(
            database_configured=False,
            detail="Set CORE_DATABASE_URL to serve SDE from Postgres.",
        )
    try:
        async with session_scope() as session:
            tc = await session.scalar(select(func.count()).select_from(SdeType))
            gc = await session.scalar(select(func.count()).select_from(SdeInvGroup))
            sc = await session.scalar(select(func.count()).select_from(SdeMapSolarSystem))
        return SdeStatusOut(
            database_configured=True,
            types=int(tc or 0),
            groups=int(gc or 0),
            solar_systems=int(sc or 0),
            detail=None if (tc or 0) > 0 else "Tables exist but are empty — run scripts/import_sde_sqlite.py.",
        )
    except Exception as exc:
        return SdeStatusOut(
            database_configured=True,
            detail=f"SDE query failed: {exc}",
        )


def _type_to_out(row: SdeType) -> SdeTypeOut:
    return SdeTypeOut(
        type_id=row.type_id,
        group_id=row.group_id,
        name=row.name,
        published=row.published,
        volume=row.volume,
        mass=row.mass,
        portion_size=row.portion_size,
        description=row.description,
        icon_url=type_icon_url(row.type_id),
        render_url=type_render_url(row.type_id),
    )


async def get_type_by_id(type_id: int) -> SdeTypeOut | None:
    async with session_scope() as session:
        row = await session.get(SdeType, type_id)
        return _type_to_out(row) if row else None


async def search_types(*, q: str, limit: int = 50) -> list[SdeTypeOut]:
    pat = f"%{q.strip()}%"
    stmt = select(SdeType).where(SdeType.name.ilike(pat)).order_by(SdeType.name).limit(limit)
    async with session_scope() as session:
        rows = (await session.scalars(stmt)).all()
        return [_type_to_out(r) for r in rows]


async def list_types_for_group(*, group_id: int, limit: int = 200) -> list[SdeTypeOut]:
    stmt = (
        select(SdeType)
        .where(SdeType.group_id == group_id)
        .order_by(SdeType.name)
        .limit(limit)
    )
    async with session_scope() as session:
        rows = (await session.scalars(stmt)).all()
        return [_type_to_out(r) for r in rows]


async def get_group_by_id(group_id: int) -> SdeInvGroupOut | None:
    async with session_scope() as session:
        row = await session.get(SdeInvGroup, group_id)
        if row is None:
            return None
        return SdeInvGroupOut(group_id=row.group_id, category_id=row.category_id, name=row.name)


async def get_solar_system_by_id(solar_system_id: int) -> SdeSolarSystemOut | None:
    async with session_scope() as session:
        row = await session.get(SdeMapSolarSystem, solar_system_id)
        if row is None:
            return None
        return SdeSolarSystemOut(
            solar_system_id=row.solar_system_id,
            name=row.name,
            security=row.security,
            constellation_id=row.constellation_id,
            region_id=row.region_id,
        )


async def get_solar_system_by_name(*, name: str) -> SdeSolarSystemOut | None:
    """Exact name match (case-insensitive)."""
    n = name.strip()
    stmt = select(SdeMapSolarSystem).where(func.lower(SdeMapSolarSystem.name) == n.lower()).limit(1)
    async with session_scope() as session:
        row = await session.scalar(stmt)
        if row is None:
            return None
        return SdeSolarSystemOut(
            solar_system_id=row.solar_system_id,
            name=row.name,
            security=row.security,
            constellation_id=row.constellation_id,
            region_id=row.region_id,
        )


async def search_solar_systems(*, q: str, limit: int = 50) -> list[SdeSolarSystemOut]:
    pat = f"%{q.strip()}%"
    stmt = (
        select(SdeMapSolarSystem)
        .where(SdeMapSolarSystem.name.ilike(pat))
        .order_by(SdeMapSolarSystem.name)
        .limit(limit)
    )
    async with session_scope() as session:
        rows = (await session.scalars(stmt)).all()
        return [
            SdeSolarSystemOut(
                solar_system_id=r.solar_system_id,
                name=r.name,
                security=r.security,
                constellation_id=r.constellation_id,
                region_id=r.region_id,
            )
            for r in rows
        ]
