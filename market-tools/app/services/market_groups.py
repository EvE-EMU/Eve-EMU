"""Market group names and hierarchy from EVE Ref reference data."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, select

from app.db.models import MarketGroup, MarketType
from app.db.session import session_scope

from app.services.catalog import (
    _save_catalog_rows,
    catalog_type_count,
    schedule_catalog_sync,
    sync_catalog_types_from_everef,
)
from app.services.everef import (
    fetch_market_group,
    fetch_type_market_groups,
    localized_name,
)
from app.services.everef_archive import (
    download_reference_archive,
    parse_catalog_types,
    parse_market_groups,
)

logger = logging.getLogger(__name__)

_groups_full_task: asyncio.Task | None = None


def full_group_sync_running() -> bool:
    return _groups_full_task is not None and not _groups_full_task.done()


async def sync_type_market_groups(*, location_id: int) -> int:
    """Resolve market_group_id for listed types (catalog first, then EVE Ref API)."""
    from app.db.models import MarketCatalogType

    async with session_scope() as session:
        type_ids = [
            int(r[0])
            for r in (
                await session.execute(
                    select(MarketType.type_id).where(
                        MarketType.location_id == location_id
                    )
                )
            ).all()
        ]
    if not type_ids:
        return 0

    group_by_type: dict[int, int | None] = {}
    async with session_scope() as session:
        cat_rows = (
            await session.execute(
                select(MarketCatalogType.type_id, MarketCatalogType.market_group_id).where(
                    MarketCatalogType.type_id.in_(type_ids)
                )
            )
        ).all()
        for tid, gid in cat_rows:
            if gid is not None:
                group_by_type[int(tid)] = int(gid)

    missing = [tid for tid in type_ids if tid not in group_by_type]
    if missing:
        group_by_type.update(await fetch_type_market_groups(missing))

    async with session_scope() as session:
        for tid, gid in group_by_type.items():
            row = await session.get(MarketType, tid)
            if row and row.location_id == location_id:
                row.market_group_id = gid

    return len(group_by_type)


async def sync_market_group_names(group_ids: set[int]) -> int:
    """Upsert group names and parents from EVE Ref (walks ancestors)."""
    pending = set(group_ids)
    seen: set[int] = set()
    rows: dict[int, MarketGroup] = {}

    while pending:
        gid = pending.pop()
        if gid in seen or gid <= 0:
            continue
        seen.add(gid)
        data = await fetch_market_group(gid)
        if not data:
            continue
        name = localized_name(data.get("name")) or f"Group {gid}"
        parent = data.get("parent_group_id")
        parent_id = int(parent) if parent is not None else None
        rows[gid] = MarketGroup(
            group_id=gid,
            name=name,
            parent_group_id=parent_id,
        )
        if parent_id and parent_id not in seen:
            pending.add(parent_id)

    if not rows:
        return 0

    async with session_scope() as session:
        for row in rows.values():
            await session.merge(row)

    return len(rows)


async def sync_listed_market_groups(*, location_id: int) -> int:
    from app.services.hub_groups import backfill_hub_market_groups_from_catalog

    await sync_type_market_groups(location_id=location_id)
    await backfill_hub_market_groups_from_catalog(location_id=location_id)
    async with session_scope() as session:
        gids = {
            int(r[0])
            for r in (
                await session.execute(
                    select(MarketType.market_group_id)
                    .where(
                        MarketType.location_id == location_id,
                        MarketType.market_group_id.isnot(None),
                    )
                    .distinct()
                )
            ).all()
            if r[0] is not None
        }
    return await sync_market_group_names(gids)


async def sync_all_market_groups_from_everef() -> int:
    """Load market groups from EVE Ref reference archive."""
    logger.info("EVE Ref: downloading reference archive for market groups")
    archive = await asyncio.to_thread(download_reference_archive)
    rows = await asyncio.to_thread(parse_market_groups, archive)
    if not rows:
        logger.warning("EVE Ref: no market groups in archive")
        return 0

    async with session_scope() as session:
        for row in rows:
            await session.merge(row)

    logger.info("EVE Ref: upserted %s market groups", len(rows))
    return len(rows)


async def sync_reference_data_from_everef() -> dict[str, int]:
    """One archive download: market groups + full type catalog."""
    logger.info("EVE Ref: downloading reference archive")
    archive = await asyncio.to_thread(download_reference_archive)
    groups = await asyncio.to_thread(parse_market_groups, archive)
    types = await asyncio.to_thread(parse_catalog_types, archive)

    if groups:
        async with session_scope() as session:
            for row in groups:
                await session.merge(row)

    type_count = 0
    if types:
        type_count = await _save_catalog_rows(types)

    logger.info(
        "EVE Ref reference sync: %s groups, %s catalog types",
        len(groups),
        type_count,
    )
    return {"groups": len(groups), "catalog_types": type_count}


async def sync_all_market_groups_from_esi() -> int:
    """Legacy alias — universe groups sync now uses EVE Ref."""
    return await sync_all_market_groups_from_everef()


async def ensure_market_groups_catalog() -> int:
    """Load EVE Ref groups + catalog if missing."""
    async with session_scope() as session:
        group_count = await session.scalar(
            select(func.count()).select_from(MarketGroup)
        ) or 0
    catalog_count = await catalog_type_count()
    if group_count > 0 and catalog_count > 0:
        return int(group_count)
    schedule_full_market_group_sync()
    return int(group_count)


async def _run_full_group_sync() -> None:
    global _groups_full_task
    try:
        await sync_reference_data_from_everef()
    except Exception:
        logger.exception("EVE Ref reference data sync failed")
    finally:
        _groups_full_task = None


def schedule_full_market_group_sync() -> None:
    """Background full tree sync (non-blocking)."""
    global _groups_full_task
    if full_group_sync_running():
        return
    _groups_full_task = asyncio.create_task(_run_full_group_sync())
