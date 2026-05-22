"""Assign market_group_id to hub listings (catalog + EVE Ref)."""

from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MarketCatalogType, MarketType
from app.db.session import session_scope
from app.services.catalog import listed_type_ids
from app.services.everef import fetch_type_market_groups

logger = logging.getLogger(__name__)


async def backfill_hub_market_groups_from_catalog(*, location_id: int) -> int:
    """Set market_group_id on hub types from market_catalog_types."""
    updated = 0
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(MarketType, MarketCatalogType.market_group_id)
                .join(
                    MarketCatalogType,
                    MarketCatalogType.type_id == MarketType.type_id,
                )
                .where(
                    MarketType.location_id == location_id,
                    MarketType.market_group_id.is_(None),
                )
            )
        ).all()
        for mt, gid in rows:
            if gid is not None:
                mt.market_group_id = int(gid)
                updated += 1
    if updated:
        logger.info("backfilled market_group_id on %s hub types", updated)
    return updated


async def hub_listed_counts_by_group(
    location_id: int,
    session: AsyncSession,
    *,
    listed: set[int] | None = None,
) -> dict[int, int]:
    """Count listed types per market group (hub rows + catalog fallback)."""
    if listed is None:
        listed = await listed_type_ids(location_id)

    hub_direct: dict[int, int] = defaultdict(int)
    assigned: set[int] = set()

    hub_rows = (
        await session.execute(
            select(MarketType.type_id, MarketType.market_group_id).where(
                MarketType.location_id == location_id
            )
        )
    ).all()
    for tid, gid in hub_rows:
        tid = int(tid)
        if tid not in listed or gid is None:
            continue
        hub_direct[int(gid)] += 1
        assigned.add(tid)

    missing = listed - assigned
    if missing:
        cat_rows = (
            await session.execute(
                select(MarketCatalogType.type_id, MarketCatalogType.market_group_id).where(
                    MarketCatalogType.type_id.in_(missing)
                )
            )
        ).all()
        for tid, gid in cat_rows:
            if gid is not None:
                hub_direct[int(gid)] += 1

    return dict(hub_direct)
