"""Wormhole map ESI location tracking."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.celery_app import celery_app
from app.db.session import get_session_factory
from app.models.tools import SdeSystem
from app.models.wormhole_map import WormholeMap, WormholeSystem
from app.services.esi import bearer_token
from app.services.wormhole_map import add_wh_system, wh_connection_manager, _system_out

logger = logging.getLogger(__name__)


async def _poll_tracking_maps() -> dict[str, int]:
    import httpx

    token = await bearer_token()
    if not token:
        return {"maps": 0, "systems_added": 0}

    factory = get_session_factory()
    added = 0
    maps: list = []
    async with factory() as session:
        maps = (
            await session.scalars(
                select(WormholeMap).where(WormholeMap.active_tracking_character_id.isnot(None))
            )
        ).all()
        headers = {"Authorization": f"Bearer {token}", "User-Agent": "EVE-EMU-EMUMS/1.0"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            for wh_map in maps:
                cid = int(wh_map.active_tracking_character_id or 0)
                if not cid:
                    continue
                resp = await client.get(
                    f"https://esi.evetech.net/latest/characters/{cid}/location/",
                    headers=headers,
                )
                if resp.status_code != 200:
                    continue
                loc = resp.json()
                solar_system_id = int(loc.get("solar_system_id") or 0)
                if not solar_system_id:
                    continue
                sde = await session.get(SdeSystem, solar_system_id)
                if not sde or sde.security >= 0:
                    continue
                existing = await session.scalar(
                    select(WormholeSystem).where(
                        WormholeSystem.map_id == wh_map.id,
                        WormholeSystem.solar_system_id == solar_system_id,
                    )
                )
                if existing:
                    continue
                row = await add_wh_system(
                    session,
                    wh_map.id,
                    solar_system_id=solar_system_id,
                    system_name=sde.name,
                    wh_class=f"C{abs(int(sde.security * 10))}" if sde.security < 0 else "",
                    space_type="j-space",
                )
                added += 1
                await wh_connection_manager.broadcast(
                    wh_map.id,
                    {"event": "system_added", "system": _system_out(row), "source": "esi_track"},
                )
        await session.commit()
    return {"maps": len(maps), "systems_added": added}


@celery_app.task(name="app.tasks.wormhole_map.poll_tracking_characters")
def poll_tracking_characters() -> dict[str, int]:
    logger.info("EMUMS: polling wormhole tracking characters")
    return asyncio.run(_poll_tracking_maps())
