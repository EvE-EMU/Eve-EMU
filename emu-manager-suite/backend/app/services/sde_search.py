"""SDE type search — DB index with fallback name resolution."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SdeTypeIndex


async def search_types(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 50,
    category: str | None = None,
    group: str | None = None,
) -> list[dict]:
    q = (query or "").strip()
    stmt = select(SdeTypeIndex)
    if category and category.strip().lower() not in ("", "all"):
        stmt = stmt.where(SdeTypeIndex.category_name == category.strip())
    if group and group.strip():
        stmt = stmt.where(SdeTypeIndex.group_name == group.strip())
    if q:
        pattern = f"%{q}%"
        filters = [
            SdeTypeIndex.name.ilike(pattern),
            SdeTypeIndex.group_name.ilike(pattern),
            SdeTypeIndex.category_name.ilike(pattern),
        ]
        if q.isdigit():
            filters.append(SdeTypeIndex.type_id == int(q))
        stmt = stmt.where(or_(*filters))
    stmt = stmt.order_by(SdeTypeIndex.name).limit(limit)
    rows = (await session.scalars(stmt)).all()
    return [
        {
            "type_id": r.type_id,
            "name": r.name,
            "group_name": r.group_name,
            "category_name": r.category_name,
            "volume_m3": r.volume_m3,
            "base_price": float(r.base_price),
        }
        for r in rows
    ]


async def list_type_categories(session: AsyncSession) -> list[str]:
    rows = (
        await session.scalars(
            select(SdeTypeIndex.category_name)
            .where(SdeTypeIndex.category_name != "")
            .distinct()
            .order_by(SdeTypeIndex.category_name)
        )
    ).all()
    return [str(r) for r in rows if r]


async def lookup_type_by_name(session_or_none, name: str) -> dict | None:
    """Lookup by exact name; accepts AsyncSession or None (returns None without DB)."""
    if session_or_none is None:
        return None
    row = await session_or_none.scalar(
        select(SdeTypeIndex).where(SdeTypeIndex.name.ilike(name.strip())).limit(1)
    )
    if not row:
        return None
    return {
        "type_id": row.type_id,
        "name": row.name,
        "group_name": row.group_name,
        "category_name": row.category_name,
    }


async def get_type(session: AsyncSession, type_id: int) -> dict | None:
    row = await session.get(SdeTypeIndex, type_id)
    if not row:
        return None
    return {
        "type_id": row.type_id,
        "name": row.name,
        "group_name": row.group_name,
        "category_name": row.category_name,
        "volume_m3": row.volume_m3,
        "base_price": float(row.base_price),
    }
