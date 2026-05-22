"""Build market group tree (all catalog types; optional listed-only filter)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MarketCatalogType, MarketGroup, MarketType
from app.services.catalog import catalog_sync_running, catalog_type_count, listed_type_ids
from app.services.hub_groups import backfill_hub_market_groups_from_catalog, hub_listed_counts_by_group


def _sort_name(item: dict[str, Any]) -> str:
    return (item.get("name") or "").lower()


async def build_market_tree(
    location_id: int,
    session: AsyncSession,
    *,
    listed_only: bool = False,
) -> dict[str, Any]:
    """
    Group hierarchy with type counts from the full EVE Ref catalog.
    Types are loaded per group via GET /browser/group/{id}/types (lazy).
    """
    groups = (
        (await session.execute(select(MarketGroup).order_by(func.lower(MarketGroup.name))))
        .scalars()
        .all()
    )
    listed = await listed_type_ids(location_id)
    if not groups:
        total = await catalog_type_count()
        return {
            "location_id": location_id,
            "total_types": total,
            "listed_types": len(listed),
            "catalog_loaded": total > 0,
            "catalog_sync_running": catalog_sync_running(),
            "children": [],
        }

    by_id = {g.group_id: g for g in groups}
    children_map: dict[int, list[int]] = defaultdict(list)
    for g in groups:
        if g.parent_group_id is not None:
            children_map[g.parent_group_id].append(g.group_id)

    direct_total: dict[int, int] = defaultdict(int)
    catalog_rows = (
        await session.execute(
            select(MarketCatalogType.market_group_id, MarketCatalogType.type_id)
        )
    ).all()
    for gid, _tid in catalog_rows:
        direct_total[int(gid)] += 1

    hub_direct = await hub_listed_counts_by_group(
        location_id, session, listed=listed
    )
    if listed and sum(hub_direct.values()) == 0:
        await backfill_hub_market_groups_from_catalog(location_id=location_id)
        hub_direct = await hub_listed_counts_by_group(
            location_id, session, listed=listed
        )

    agg_cache: dict[int, tuple[int, int]] = {}

    def aggregate(group_id: int) -> tuple[int, int]:
        if group_id in agg_cache:
            return agg_cache[group_id]
        total = direct_total.get(group_id, 0)
        listed_n = hub_direct.get(group_id, 0)
        for cid in children_map.get(group_id, []):
            t, l = aggregate(cid)
            total += t
            listed_n += l
        agg_cache[group_id] = (total, listed_n)
        return total, listed_n

    def build_node(group_id: int) -> dict[str, Any] | None:
        g = by_id.get(group_id)
        if not g:
            return None
        total, listed_n = aggregate(group_id)
        if listed_only and listed_n == 0:
            return None
        child_nodes: list[dict[str, Any]] = []
        for cid in children_map.get(group_id, []):
            node = build_node(cid)
            if node:
                child_nodes.append(node)
        child_nodes.sort(key=_sort_name)
        return {
            "kind": "group",
            "group_id": g.group_id,
            "name": g.name,
            "count": total,
            "listed_count": listed_n,
            "direct_count": direct_total.get(group_id, 0),
            "direct_listed_count": hub_direct.get(group_id, 0),
            "children": child_nodes,
        }

    root_ids = [g.group_id for g in groups if g.parent_group_id is None]
    root_nodes = []
    for gid in root_ids:
        node = build_node(gid)
        if node:
            root_nodes.append(node)
    root_nodes.sort(key=_sort_name)

    catalog_total = await catalog_type_count()
    hub_listed = sum(hub_direct.values()) or len(listed)
    return {
        "location_id": location_id,
        "total_types": catalog_total,
        "listed_types": hub_listed,
        "catalog_loaded": catalog_total > 0,
        "catalog_sync_running": catalog_sync_running(),
        "children": root_nodes,
    }
