"""ESI sovereignty map → system tags."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.intel_store import add_system_tag

logger = logging.getLogger(__name__)

_alliance_names: dict[int, str] = {}


async def _esi_post_names(ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    url = f"{settings.esi_base_url.rstrip('/')}/universe/names/"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url,
            params={"datasource": settings.esi_datasource},
            json=ids,
        )
        resp.raise_for_status()
        return resp.json()


async def _esi_get(path: str) -> Any:
    url = f"{settings.esi_base_url.rstrip('/')}/{path.lstrip('/')}"
    params = {"datasource": settings.esi_datasource}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def refresh_sov_tags(session: AsyncSession) -> int:
    """Tag systems held by configured alliances (sov:ALLIANCE_TICKER)."""
    alliance_ids = set(settings.sov_alliance_id_list())
    if not alliance_ids:
        return 0

    sov_rows = await _esi_get("sovereignty/map/")
    if not isinstance(sov_rows, list):
        return 0

    held: dict[int, int] = {}
    for row in sov_rows:
        aid = row.get("alliance_id")
        sid = row.get("system_id")
        if aid and sid and int(aid) in alliance_ids:
            held[int(sid)] = int(aid)

    if not held:
        return 0

    name_ids = sorted(set(held.values()))
    for i in range(0, len(name_ids), 1000):
        for row in await _esi_post_names(name_ids[i : i + 1000]):
            if row.get("category") == "alliance":
                _alliance_names[int(row["id"])] = str(row["name"])

    count = 0
    for system_id, aid in held.items():
        label = _alliance_names.get(aid, f"Alliance {aid}")
        tag = f"sov:{label}"
        await add_system_tag(session, solar_system_id=system_id, tag=tag, source="sov")
        count += 1
    logger.info("Refreshed %s sov system tags for alliances %s", count, alliance_ids)
    return count
