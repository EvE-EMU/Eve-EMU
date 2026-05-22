"""Full marketable type catalog from EVE Ref (all items in market groups)."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import delete, func, select

from app.db.models import MarketCatalogType, MarketOrder, MarketType
from app.db.session import session_scope
from app.services.everef_archive import (
    download_reference_archive,
    parse_catalog_types,
)

logger = logging.getLogger(__name__)

_catalog_task: asyncio.Task | None = None
_DB_BATCH = 3000


def catalog_sync_running() -> bool:
    return _catalog_task is not None and not _catalog_task.done()


async def _save_catalog_rows(rows: list[MarketCatalogType]) -> int:
    if not rows:
        return 0
    async with session_scope() as session:
        await session.execute(delete(MarketCatalogType))
    for i in range(0, len(rows), _DB_BATCH):
        batch = rows[i : i + _DB_BATCH]
        async with session_scope() as session:
            session.add_all(batch)
    return len(rows)


async def sync_catalog_types_from_everef(*, replace: bool = True) -> int:
    """Import published marketable types from EVE Ref reference archive."""
    logger.info("EVE Ref catalog: downloading reference archive")
    archive = await asyncio.to_thread(download_reference_archive)
    rows = await asyncio.to_thread(parse_catalog_types, archive)
    if not rows:
        logger.warning("EVE Ref catalog: no marketable types in archive")
        return 0
    logger.info("EVE Ref catalog: saving %s types", len(rows))
    if replace:
        return await _save_catalog_rows(rows)
    async with session_scope() as session:
        for row in rows:
            await session.merge(row)
    return len(rows)


async def catalog_type_count() -> int:
    async with session_scope() as session:
        return int(
            await session.scalar(select(func.count()).select_from(MarketCatalogType)) or 0
        )


async def _run_catalog_sync() -> None:
    global _catalog_task
    try:
        n = await sync_catalog_types_from_everef()
        logger.info("EVE Ref catalog sync finished: %s types", n)
    except Exception:
        logger.exception("EVE Ref catalog sync failed")
    finally:
        _catalog_task = None


def schedule_catalog_sync() -> None:
    global _catalog_task
    if catalog_sync_running():
        return
    _catalog_task = asyncio.create_task(_run_catalog_sync())


async def ensure_catalog_loaded() -> int:
    count = await catalog_type_count()
    if count > 0:
        return count
    schedule_catalog_sync()
    return 0


async def listed_type_ids(location_id: int) -> set[int]:
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(MarketOrder.type_id)
                .where(MarketOrder.location_id == location_id)
                .distinct()
            )
        ).all()
    return {int(r[0]) for r in rows}


async def group_types(
    *,
    group_id: int,
    location_id: int,
    listed_only: bool = False,
) -> list[dict]:
    listed = await listed_type_ids(location_id)
    async with session_scope() as session:
        if listed_only:
            if not listed:
                return []
            hub_names = {
                int(t.type_id): t.name
                for t in (
                    await session.execute(
                        select(MarketType).where(
                            MarketType.location_id == location_id,
                            MarketType.type_id.in_(listed),
                        )
                    )
                )
                .scalars()
                .all()
            }
            cat_rows = (
                await session.execute(
                    select(MarketCatalogType)
                    .where(
                        MarketCatalogType.market_group_id == group_id,
                        MarketCatalogType.type_id.in_(listed),
                    )
                    .order_by(func.lower(MarketCatalogType.name))
                )
            ).scalars().all()
            return [
                {
                    "kind": "type",
                    "type_id": t.type_id,
                    "name": hub_names.get(t.type_id) or t.name,
                    "listed": True,
                }
                for t in cat_rows
            ]

        rows = (
            await session.execute(
                select(MarketCatalogType)
                .where(MarketCatalogType.market_group_id == group_id)
                .order_by(func.lower(MarketCatalogType.name))
            )
        ).scalars().all()

    return [
        {
            "kind": "type",
            "type_id": t.type_id,
            "name": t.name,
            "listed": t.type_id in listed,
        }
        for t in rows
    ]


async def search_catalog_types(
    *,
    query: str,
    limit: int = 40,
    listed_only: bool = False,
    location_id: int,
) -> list[dict]:
    q = (query or "").strip().lower()
    listed = await listed_type_ids(location_id)
    if listed_only and not listed:
        return []
    async with session_scope() as session:
        stmt = select(MarketCatalogType)
        if q:
            stmt = stmt.where(MarketCatalogType.name_lower.contains(q))
        if listed_only:
            stmt = stmt.where(MarketCatalogType.type_id.in_(listed))
        stmt = stmt.order_by(MarketCatalogType.name).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "type_id": t.type_id,
            "name": t.name,
            "listed": t.type_id in listed,
        }
        for t in rows
    ]


async def catalog_type_name(type_id: int) -> str | None:
    async with session_scope() as session:
        row = await session.get(MarketCatalogType, type_id)
    return row.name if row else None
