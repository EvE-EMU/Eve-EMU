"""Market group names and hierarchy from public ESI."""

from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy import select

from app.db.models import MarketGroup, MarketType
from app.db.session import session_scope
from app.esi.rate_limit import acquire_slot

logger = logging.getLogger(__name__)
_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-Market/1.0"
_CONCURRENT = 8


async def _esi_get_type_market_group(type_id: int) -> tuple[int, int | None]:
    await acquire_slot()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{_ESI}/universe/types/{type_id}/",
            headers={"Accept": "application/json", "User-Agent": _UA},
        )
    if resp.status_code != 200:
        return type_id, None
    row = resp.json()
    if not isinstance(row, dict):
        return type_id, None
    mg = row.get("market_group_id")
    return type_id, int(mg) if mg is not None else None


async def _fetch_type_market_groups(type_ids: list[int]) -> dict[int, int | None]:
    if not type_ids:
        return {}
    sem = asyncio.Semaphore(_CONCURRENT)

    async def _one(tid: int) -> tuple[int, int | None]:
        async with sem:
            return await _esi_get_type_market_group(tid)

    pairs = await asyncio.gather(*[_one(tid) for tid in type_ids])
    return dict(pairs)


async def _esi_get_group(group_id: int) -> tuple[str, int | None] | None:
    await acquire_slot()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{_ESI}/universe/groups/{group_id}/",
            headers={"Accept": "application/json", "User-Agent": _UA},
        )
    if resp.status_code != 200:
        return None
    row = resp.json()
    if not isinstance(row, dict):
        return None
    name = str(row.get("name") or f"Group {group_id}").strip()
    parent = row.get("parent_group_id")
    return name, int(parent) if parent is not None else None


async def sync_type_market_groups(*, location_id: int) -> int:
    """Resolve market_group_id for listed types at a hub."""
    async with session_scope() as session:
        type_ids = [
            int(r[0])
            for r in (
                await session.execute(
                    select(MarketType.type_id).where(MarketType.location_id == location_id)
                )
            ).all()
        ]
    if not type_ids:
        return 0

    group_by_type = await _fetch_type_market_groups(type_ids)

    async with session_scope() as session:
        for tid, gid in group_by_type.items():
            row = await session.get(MarketType, tid)
            if row and row.location_id == location_id:
                row.market_group_id = gid

    return len(group_by_type)


async def sync_market_group_names(group_ids: set[int]) -> int:
    """Upsert group names and parents (walks up the chain)."""
    pending = set(group_ids)
    seen: set[int] = set()
    rows: dict[int, MarketGroup] = {}

    while pending:
        gid = pending.pop()
        if gid in seen or gid <= 0:
            continue
        seen.add(gid)
        info = await _esi_get_group(gid)
        if not info:
            continue
        name, parent = info
        rows[gid] = MarketGroup(group_id=gid, name=name, parent_group_id=parent)
        if parent and parent not in seen:
            pending.add(parent)

    if not rows:
        return 0

    async with session_scope() as session:
        for row in rows.values():
            await session.merge(row)

    return len(rows)


async def sync_listed_market_groups(*, location_id: int) -> int:
    await sync_type_market_groups(location_id=location_id)
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
