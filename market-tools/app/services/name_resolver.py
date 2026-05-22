"""Resolve EVE type IDs to display names (hub cache + catalog)."""

from __future__ import annotations

from sqlalchemy import select

from app.db.models import MarketCatalogType, MarketType
from app.db.session import session_scope


def display_name(type_id: int, hub_name: str | None, catalog_name: str | None) -> str:
    def usable(label: str | None) -> bool:
        if not label or not str(label).strip():
            return False
        s = str(label).strip()
        return s != str(type_id) and s != f"Type {type_id}"

    if usable(catalog_name):
        return str(catalog_name).strip()
    if usable(hub_name):
        return str(hub_name).strip()
    return str(catalog_name or hub_name or f"Type {type_id}").strip()


async def catalog_names(type_ids: list[int]) -> dict[int, str]:
    if not type_ids:
        return {}
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(MarketCatalogType.type_id, MarketCatalogType.name).where(
                    MarketCatalogType.type_id.in_(type_ids)
                )
            )
        ).all()
    return {int(r.type_id): r.name for r in rows}


async def hub_names(location_id: int, type_ids: list[int]) -> dict[int, str]:
    if not type_ids:
        return {}
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(MarketType.type_id, MarketType.name).where(
                    MarketType.location_id == location_id,
                    MarketType.type_id.in_(type_ids),
                )
            )
        ).all()
    return {int(r.type_id): r.name for r in rows if r.name}


async def attach_type_names(
    rows: list[dict],
    *,
    location_id: int,
    id_key: str = "type_id",
    name_key: str = "type_name",
) -> None:
    if not rows:
        return
    tids = [int(r[id_key]) for r in rows]
    cat = await catalog_names(tids)
    hub = await hub_names(location_id, tids)
    for row in rows:
        tid = int(row[id_key])
        row[name_key] = display_name(tid, hub.get(tid), cat.get(tid))
