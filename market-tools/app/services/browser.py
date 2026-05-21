"""Market browser aggregates (orders + catalog by item name)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.db.models import MarketGroup, MarketOrder, MarketType, TypeAppraisal
from app.db.session import session_scope
from app.services.market_history import resolve_hub_region_id, type_history


async def listed_types_catalog(*, location_id: int) -> dict:
    """All types with active orders at the hub, with best bid/ask."""
    async with session_scope() as session:
        sell_sq = (
            select(
                MarketOrder.type_id,
                func.min(MarketOrder.price).label("best_sell"),
                func.sum(MarketOrder.volume_remain).label("sell_vol"),
            )
            .where(MarketOrder.location_id == location_id, MarketOrder.is_buy.is_(False))
            .group_by(MarketOrder.type_id)
            .subquery()
        )
        buy_sq = (
            select(
                MarketOrder.type_id,
                func.max(MarketOrder.price).label("best_buy"),
                func.sum(MarketOrder.volume_remain).label("buy_vol"),
            )
            .where(MarketOrder.location_id == location_id, MarketOrder.is_buy.is_(True))
            .group_by(MarketOrder.type_id)
            .subquery()
        )
        q = (
            select(
                MarketType.type_id,
                MarketType.name,
                MarketType.market_group_id,
                sell_sq.c.best_sell,
                sell_sq.c.sell_vol,
                buy_sq.c.best_buy,
                buy_sq.c.buy_vol,
            )
            .where(MarketType.location_id == location_id)
            .outerjoin(sell_sq, sell_sq.c.type_id == MarketType.type_id)
            .outerjoin(buy_sq, buy_sq.c.type_id == MarketType.type_id)
            .order_by(MarketType.name)
        )
        rows = (await session.execute(q)).all()

    types = []
    for r in rows:
        types.append(
            {
                "type_id": int(r.type_id),
                "name": r.name,
                "market_group_id": int(r.market_group_id) if r.market_group_id else None,
                "best_sell": float(r.best_sell) if r.best_sell is not None else None,
                "best_buy": float(r.best_buy) if r.best_buy is not None else None,
                "sell_volume": int(r.sell_vol or 0),
                "buy_volume": int(r.buy_vol or 0),
            }
        )
    return {"location_id": location_id, "count": len(types), "types": types}


async def _type_rows_with_prices(session, location_id: int, type_ids: list[int]) -> dict[int, dict]:
    if not type_ids:
        return {}
    sell = {
        int(r.type_id): (float(r.best_sell), int(r.sell_vol or 0))
        for r in (
            await session.execute(
                select(
                    MarketOrder.type_id,
                    func.min(MarketOrder.price).label("best_sell"),
                    func.sum(MarketOrder.volume_remain).label("sell_vol"),
                )
                .where(
                    MarketOrder.location_id == location_id,
                    MarketOrder.type_id.in_(type_ids),
                    MarketOrder.is_buy.is_(False),
                )
                .group_by(MarketOrder.type_id)
            )
        ).all()
    }
    buy = {
        int(r.type_id): (float(r.best_buy), int(r.buy_vol or 0))
        for r in (
            await session.execute(
                select(
                    MarketOrder.type_id,
                    func.max(MarketOrder.price).label("best_buy"),
                    func.sum(MarketOrder.volume_remain).label("buy_vol"),
                )
                .where(
                    MarketOrder.location_id == location_id,
                    MarketOrder.type_id.in_(type_ids),
                    MarketOrder.is_buy.is_(True),
                )
                .group_by(MarketOrder.type_id)
            )
        ).all()
    }
    out: dict[int, dict] = {}
    for tid in type_ids:
        s = sell.get(tid)
        b = buy.get(tid)
        out[tid] = {
            "best_sell": s[0] if s else None,
            "sell_volume": s[1] if s else 0,
            "best_buy": b[0] if b else None,
            "buy_volume": b[1] if b else 0,
        }
    return out


async def search_listed_types(
    *,
    location_id: int,
    query: str,
    limit: int = 40,
) -> list[dict]:
    q = (query or "").strip().lower()
    async with session_scope() as session:
        stmt = select(MarketType).where(MarketType.location_id == location_id)
        if q:
            stmt = stmt.where(MarketType.name_lower.contains(q))
        stmt = stmt.order_by(MarketType.name).limit(limit)
        types = (await session.execute(stmt)).scalars().all()
        prices = await _type_rows_with_prices(
            session, location_id, [t.type_id for t in types]
        )
    return [
        {
            "type_id": t.type_id,
            "name": t.name,
            **prices.get(t.type_id, {}),
        }
        for t in types
    ]


async def resolve_type_id(
    *,
    location_id: int,
    type_id: int | None = None,
    name: str | None = None,
) -> int | None:
    if type_id:
        return int(type_id)
    needle = (name or "").strip().lower()
    if not needle:
        return None
    async with session_scope() as session:
        exact = await session.scalar(
            select(MarketType.type_id)
            .where(
                MarketType.location_id == location_id,
                MarketType.name_lower == needle,
            )
            .limit(1)
        )
        if exact:
            return int(exact)
        partial = await session.scalar(
            select(MarketType.type_id)
            .where(
                MarketType.location_id == location_id,
                MarketType.name_lower.contains(needle),
            )
            .order_by(MarketType.name)
            .limit(1)
        )
        return int(partial) if partial else None


async def item_orders(
    *,
    location_id: int,
    type_id: int,
) -> dict:
    async with session_scope() as session:
        q = select(MarketOrder).where(
            MarketOrder.location_id == location_id,
            MarketOrder.type_id == type_id,
        )
        orders = (await session.execute(q)).scalars().all()
        appr = await session.scalar(
            select(TypeAppraisal).where(TypeAppraisal.type_id == type_id).limit(1)
        )
        type_name = await session.scalar(
            select(MarketType.name)
            .where(
                MarketType.type_id == type_id,
                MarketType.location_id == location_id,
            )
            .limit(1)
        )
    sells = sorted(
        [o for o in orders if not o.is_buy],
        key=lambda x: x.price,
    )
    buys = sorted(
        [o for o in orders if o.is_buy],
        key=lambda x: x.price,
        reverse=True,
    )

    def _row(o: MarketOrder) -> dict:
        return {
            "order_id": o.order_id,
            "price": o.price,
            "volume_remain": o.volume_remain,
            "min_volume": o.min_volume,
            "range": o.range,
            "issued": o.issued.isoformat() if o.issued else None,
        }

    return {
        "type_id": type_id,
        "type_name": type_name or f"Type {type_id}",
        "location_id": location_id,
        "sell_orders": [_row(o) for o in sells],
        "buy_orders": [_row(o) for o in buys],
        "order_counts": {"sell": len(sells), "buy": len(buys)},
        "history": await type_history(type_id=type_id),
        "hub_region_id": await resolve_hub_region_id(),
        "appraisal": {
            "wompstar_sell": appr.wompstar_sell if appr else None,
            "wompstar_buy": appr.wompstar_buy if appr else None,
            "jita_sell": appr.jita_sell if appr else None,
            "jita_buy": appr.jita_buy if appr else None,
        }
        if appr
        else None,
    }


async def listed_types_category_tree(*, location_id: int) -> dict:
    """Nested market-group tree containing only types listed at the hub."""
    catalog = await listed_types_catalog(location_id=location_id)
    types = catalog["types"]
    if not types:
        return {"location_id": location_id, "tree": []}

    group_ids = {t["market_group_id"] for t in types if t.get("market_group_id")}
    groups: dict[int, MarketGroup] = {}
    if group_ids:
        async with session_scope() as session:
            rows = (
                await session.execute(
                    select(MarketGroup).where(MarketGroup.group_id.in_(group_ids))
                )
            ).scalars().all()
            groups = {g.group_id: g for g in rows}

    by_group: dict[int | None, list[dict]] = {}
    for t in types:
        by_group.setdefault(t.get("market_group_id"), []).append(t)

    nodes: dict[int, dict] = {}
    for gid, g in groups.items():
        nodes[gid] = {
            "id": f"g:{gid}",
            "kind": "group",
            "name": g.name,
            "group_id": gid,
            "children": [],
        }

    roots: list[dict] = []
    for gid, node in nodes.items():
        parent = groups[gid].parent_group_id
        if parent and parent in nodes:
            nodes[parent]["children"].append(node)
        else:
            roots.append(node)

    for gid, items in by_group.items():
        if gid is None or gid not in nodes:
            continue
        for t in sorted(items, key=lambda x: x["name"].lower()):
            nodes[gid]["children"].append(
                {
                    "id": f"t:{t['type_id']}",
                    "kind": "type",
                    "name": t["name"],
                    "type_id": t["type_id"],
                    "best_sell": t.get("best_sell"),
                    "best_buy": t.get("best_buy"),
                }
            )

    other = by_group.get(None) or []
    if other:
        roots.append(
            {
                "id": "g:other",
                "kind": "group",
                "name": "Other",
                "children": [
                    {
                        "id": f"t:{t['type_id']}",
                        "kind": "type",
                        "name": t["name"],
                        "type_id": t["type_id"],
                        "best_sell": t.get("best_sell"),
                        "best_buy": t.get("best_buy"),
                    }
                    for t in sorted(other, key=lambda x: x["name"].lower())
                ],
            }
        )

    def _prune(node: dict) -> bool:
        kids = node.get("children") or []
        kept = [c for c in kids if c.get("kind") == "type" or _prune(c)]
        node["children"] = sorted(
            [c for c in kept if c.get("kind") == "group"],
            key=lambda x: x["name"].lower(),
        ) + sorted(
            [c for c in kept if c.get("kind") == "type"],
            key=lambda x: x["name"].lower(),
        )
        return node.get("kind") == "type" or bool(node["children"])

    roots = [r for r in roots if _prune(r)]
    roots.sort(key=lambda x: x["name"].lower())

    return {"location_id": location_id, "count": len(types), "tree": roots}
