"""Resolve inventory type IDs to names via public ESI."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import delete, select

from app.db.models import MarketOrder, MarketType
from app.db.session import session_scope
from app.esi.rate_limit import acquire_slot

logger = logging.getLogger(__name__)
_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-Market/1.0"
_CHUNK = 1000


async def _esi_universe_names(type_ids: list[int]) -> dict[int, str]:
    if not type_ids:
        return {}
    await acquire_slot()
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            f"{_ESI}/universe/names/",
            json=type_ids,
            headers={"Accept": "application/json", "User-Agent": _UA},
        )
    if resp.status_code != 200:
        logger.warning("universe/names %s: %s", resp.status_code, resp.text[:200])
        return {}
    out: dict[int, str] = {}
    for row in resp.json():
        if not isinstance(row, dict):
            continue
        if row.get("category") != "inventory_type":
            continue
        try:
            tid = int(row["id"])
            name = str(row.get("name") or "").strip()
        except (KeyError, TypeError, ValueError):
            continue
        if name:
            out[tid] = name
    return out


async def sync_listed_type_names(*, location_id: int) -> int:
    """Upsert names for every type_id with orders at this structure."""
    async with session_scope() as session:
        type_ids = [
            int(r[0])
            for r in (
                await session.execute(
                    select(MarketOrder.type_id)
                    .where(MarketOrder.location_id == location_id)
                    .distinct()
                )
            ).all()
        ]

    if not type_ids:
        await _clear_types_for_location(location_id)
        return 0

    names: dict[int, str] = {}
    for i in range(0, len(type_ids), _CHUNK):
        chunk = type_ids[i : i + _CHUNK]
        names.update(await _esi_universe_names(chunk))

    rows: list[MarketType] = []
    for tid in type_ids:
        label = names.get(tid) or f"Type {tid}"
        rows.append(
            MarketType(
                type_id=tid,
                location_id=location_id,
                name=label,
                name_lower=label.lower(),
            )
        )

    async with session_scope() as session:
        await session.execute(delete(MarketType).where(MarketType.location_id == location_id))
        if rows:
            session.add_all(rows)

    logger.info("type names: %d types at location %s", len(rows), location_id)
    return len(rows)


async def _clear_types_for_location(location_id: int) -> None:
    async with session_scope() as session:
        await session.execute(delete(MarketType).where(MarketType.location_id == location_id))
