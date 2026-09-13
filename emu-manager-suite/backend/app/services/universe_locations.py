"""Cached station/structure/system names from ESI."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member_audit import UniverseLocation
from app.services.esi import bearer_token, resolve_universe_names

logger = logging.getLogger(__name__)
_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; audit)"

STALE_DAYS = 7


def _station_id(entity_id: int) -> bool:
    return 60_000_000 <= entity_id < 64_000_000


async def _resolve_station(client: httpx.AsyncClient, station_id: int) -> dict | None:
    resp = await client.get(
        f"{_ESI}/universe/stations/{station_id}/",
        headers={"Accept": "application/json", "User-Agent": _UA},
    )
    if resp.status_code != 200:
        return None
    body = resp.json()
    if not isinstance(body, dict):
        return None
    return {
        "entity_id": station_id,
        "name": str(body.get("name") or f"Station {station_id}"),
        "entity_type": "station",
        "solar_system_id": int(body.get("system_id") or 0) or None,
    }


async def _resolve_structure(
    client: httpx.AsyncClient,
    structure_id: int,
    *,
    token: str | None,
) -> dict | None:
    headers = {"Accept": "application/json", "User-Agent": _UA}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = await client.get(f"{_ESI}/universe/structures/{structure_id}/", headers=headers)
    if resp.status_code != 200:
        return None
    body = resp.json()
    if not isinstance(body, dict):
        return None
    return {
        "entity_id": structure_id,
        "name": str(body.get("name") or f"Structure {structure_id}"),
        "entity_type": "structure",
        "solar_system_id": int(body.get("solar_system_id") or 0) or None,
    }


async def ensure_universe_locations(
    session: AsyncSession,
    entity_ids: list[int],
    *,
    character_id: int | None = None,
    access_token: str | None = None,
    force: bool = False,
) -> dict[int, UniverseLocation]:
    unique = sorted({int(i) for i in entity_ids if int(i) > 0})
    if not unique:
        return {}

    existing_rows = (
        await session.scalars(
            select(UniverseLocation).where(UniverseLocation.entity_id.in_(unique))
        )
    ).all()
    by_id = {int(r.entity_id): r for r in existing_rows}
    stale_cutoff = datetime.now(UTC) - timedelta(days=STALE_DAYS)
    need: list[int] = []
    for eid in unique:
        row = by_id.get(eid)
        if force or row is None:
            need.append(eid)
        elif row.updated_at and row.updated_at.replace(tzinfo=UTC) < stale_cutoff:
            need.append(eid)

    if need:
        tokens: list[str] = []
        seen_tokens: set[str] = set()

        async def _add_token(tok: str | None) -> None:
            if tok and tok not in seen_tokens:
                seen_tokens.add(tok)
                tokens.append(tok)

        primary = access_token or (
            await bearer_token(session, character_id=character_id) if character_id else None
        )
        await _add_token(primary)
        if character_id:
            from app.services.character_roster import roster_character_ids

            for cid in sorted(await roster_character_ids(session, character_id)):
                if cid == character_id:
                    continue
                await _add_token(await bearer_token(session, character_id=cid))

        async with httpx.AsyncClient(timeout=45.0) as client:
            name_map = await resolve_universe_names(need)
            for eid in need:
                meta: dict | None = None
                if _station_id(eid):
                    meta = await _resolve_station(client, eid)
                elif eid >= 1_000_000_000_000:
                    for tok in tokens:
                        meta = await _resolve_structure(client, eid, token=tok)
                        if meta:
                            break
                    if not meta:
                        meta = await _resolve_structure(client, eid, token=primary)
                elif eid < 70_000_000:
                    meta = {
                        "entity_id": eid,
                        "name": name_map.get(eid, f"System {eid}"),
                        "entity_type": "solar_system",
                        "solar_system_id": eid,
                    }
                else:
                    meta = {
                        "entity_id": eid,
                        "name": name_map.get(eid, f"Location {eid}"),
                        "entity_type": "unknown",
                        "solar_system_id": None,
                    }
                if not meta:
                    meta = {
                        "entity_id": eid,
                        "name": name_map.get(eid, f"Location {eid}"),
                        "entity_type": "unknown",
                        "solar_system_id": None,
                    }
                row = by_id.get(eid)
                if row is None:
                    row = UniverseLocation(entity_id=eid)
                    session.add(row)
                    by_id[eid] = row
                row.name = meta["name"]
                row.entity_type = meta.get("entity_type") or ""
                row.solar_system_id = meta.get("solar_system_id")
                row.updated_at = datetime.now(UTC)

    return by_id


async def refresh_stale_universe_locations(session: AsyncSession) -> int:
    stale_cutoff = datetime.now(UTC) - timedelta(days=STALE_DAYS)
    rows = (
        await session.scalars(
            select(UniverseLocation).where(
                UniverseLocation.updated_at.is_(None)
                | (UniverseLocation.updated_at < stale_cutoff)
            )
        )
    ).all()
    ids = [int(r.entity_id) for r in rows]
    if not ids:
        return 0
    await ensure_universe_locations(session, ids, force=True)
    return len(ids)
