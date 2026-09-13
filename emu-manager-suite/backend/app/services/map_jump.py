"""Resolve systems and ship slugs for map endpoints."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tools import SdeSystem
from app.services.jump_ship_specs import list_jump_ship_specs


SHIP_CLASS_DEFAULTS: dict[str, str] = {
    "dreadnought": "revelation",
    "dread": "revelation",
    "carrier": "archon",
    "supercarrier": "nyx",
    "super": "nyx",
    "titan": "avatar",
    "jump freighter": "nomad",
    "jumpfreighter": "nomad",
    "jf": "nomad",
    "black ops": "widow",
    "blops": "widow",
    "rorqual": "rorqual",
    "industrial cap": "rorqual",
}


async def resolve_system_id(session: AsyncSession, ref: str | int) -> int | None:
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        sid = int(ref)
        row = await session.get(SdeSystem, sid)
        return sid if row else None
    needle = str(ref).strip()
    if not needle:
        return None
    row = await session.scalar(
        select(SdeSystem)
        .where(or_(SdeSystem.name.ilike(needle), SdeSystem.name.ilike(f"{needle}%")))
        .order_by(SdeSystem.name)
        .limit(1)
    )
    return row.system_id if row else None


def resolve_ship_slug(*, ship_class: str | None, ship_slug: str | None) -> str | None:
    if ship_slug:
        return ship_slug.strip().lower()
    if not ship_class:
        return None
    key = ship_class.strip().lower()
    if key in SHIP_CLASS_DEFAULTS:
        return SHIP_CLASS_DEFAULTS[key]
    for ship in list_jump_ship_specs():
        if ship["category"].lower() == key or ship["name"].lower() == key:
            return ship["slug"]
        if key in ship["name"].lower():
            return ship["slug"]
    return None
