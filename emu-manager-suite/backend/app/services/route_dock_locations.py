"""Dock locations for route planning — coalition structures and NPC trade hubs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthedStructure, SsoUser
from app.services.market_browser import NPC_MARKET_HUBS

# Primary NPC hub solar system IDs (Tranquility SDE).
NPC_HUB_SYSTEMS: dict[str, tuple[int, str]] = {
    "jita": (30000142, "Jita"),
    "amarr": (30002187, "Amarr"),
    "dodixie": (30002659, "Dodixie"),
    "rens": (30002510, "Rens"),
    "hek": (30002053, "Hek"),
}


async def list_dock_locations(
    session: AsyncSession,
    *,
    character_id: int | None = None,
) -> dict[str, Any]:
    """Return docking options: coalition structures when authed, always NPC hubs."""
    viewer: SsoUser | None = None
    if character_id:
        viewer = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    if viewer is None:
        viewer = await session.scalar(select(SsoUser).limit(1))

    npc: list[dict[str, Any]] = []
    seen_systems: set[int] = set()
    for slug, (system_id, system_name) in NPC_HUB_SYSTEMS.items():
        hub = NPC_MARKET_HUBS.get(slug, {})
        stations = hub.get("stations") or []
        station_id, station_name = stations[0] if stations else (None, f"{system_name} (NPC)")
        if system_id in seen_systems:
            continue
        seen_systems.add(system_id)
        npc.append(
            {
                "id": f"npc:{system_id}",
                "kind": "npc_station",
                "system_id": system_id,
                "system_name": system_name,
                "label": station_name,
                "station_id": station_id,
                "region_name": hub.get("region_name", ""),
            }
        )

    structures: list[dict[str, Any]] = []
    rows = (await session.scalars(select(AuthedStructure).order_by(AuthedStructure.structure_name))).all()
    for s in rows:
        owner_name = None
        if s.owner_character_id:
            owner = await session.scalar(
                select(SsoUser).where(SsoUser.character_id == s.owner_character_id)
            )
            if owner:
                owner_name = owner.character_name
        structures.append(
            {
                "id": f"structure:{s.structure_id}",
                "kind": "structure",
                "structure_id": s.structure_id,
                "system_id": s.solar_system_id or None,
                "system_name": s.system_name,
                "label": s.structure_name,
                "has_market": s.has_market,
                "has_reprocessing": s.has_reprocessing,
                "owner_character_name": owner_name,
            }
        )

    authenticated = viewer is not None
    return {
        "authenticated": authenticated,
        "character_id": viewer.character_id if viewer else None,
        "character_name": viewer.character_name if viewer else None,
        "corporation_id": viewer.corporation_id if viewer else None,
        "corporation_name": viewer.corporation_name if viewer else None,
        "alliance_id": viewer.alliance_id if viewer else None,
        "alliance_name": viewer.alliance_name if viewer else None,
        "npc_stations": npc,
        "structures": structures if authenticated else [],
        "note": None if authenticated else "Log in to include coalition structure docking access.",
    }
