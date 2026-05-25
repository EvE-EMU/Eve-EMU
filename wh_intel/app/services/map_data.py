"""Load jump graph + system coordinates from ESI / optional SDE SQLite."""

from __future__ import annotations

import logging
import math
import sqlite3
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import MapJump, MapSystem, ServiceMeta

logger = logging.getLogger(__name__)


async def _esi_get(path: str):
    url = f"{settings.esi_base_url.rstrip('/')}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url, params={"datasource": settings.esi_datasource})
        resp.raise_for_status()
        return resp.json()


def _load_coords_from_sqlite(path: Path) -> dict[int, tuple[float, float, float, str, float]]:
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.execute(
            'SELECT "solarSystemID", "solarSystemName", "security", "x", "y", "regionID" '
            'FROM "mapSolarSystems"'
        )
        out: dict[int, tuple[float, float, float, str, float]] = {}
        for row in cur:
            out[int(row[0])] = (
                float(row[3]),
                float(row[4]),
                float(row[5]),
                str(row[1]),
                float(row[2] or 0),
            )
        return out
    finally:
        conn.close()


def _load_jumps_from_sqlite(path: Path) -> list[tuple[int, int]]:
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.execute(
            'SELECT "fromSolarSystemID", "toSolarSystemID" FROM "mapSolarSystemJumps"'
        )
        return [(int(a), int(b)) for a, b in cur.fetchall()]
    finally:
        conn.close()


async def _map_graph_bootstrapped(session: AsyncSession) -> bool:
    row = await session.get(ServiceMeta, "map_graph")
    return row is not None


async def _mark_map_graph_bootstrapped(session: AsyncSession, source: str) -> None:
    session.add(ServiceMeta(key="map_graph", value=source))
    await session.flush()


async def ensure_systems(
    session: AsyncSession,
    systems: dict[int, str],
) -> None:
    """Ensure intel systems exist in map_systems (coords from ESI if missing)."""
    for sid, name in systems.items():
        if await session.get(MapSystem, sid):
            continue
        sec = 0.0
        region_id = None
        try:
            info = await _esi_get(f"universe/systems/{sid}/")
            name = str(info.get("name") or name)
            sec = float(info.get("security_status") or 0)
            region_id = info.get("constellation_id")
        except Exception:
            logger.warning("ESI system lookup failed for %s", sid)
        angle = (sid % 360) * math.pi / 180.0
        session.add(
            MapSystem(
                solar_system_id=sid,
                name=name,
                security=sec,
                region_id=region_id,
                x=math.cos(angle) * 1000,
                y=math.sin(angle) * 1000,
            )
        )
    await session.flush()


async def ensure_map_data(session: AsyncSession) -> None:
    if await _map_graph_bootstrapped(session):
        return

    sqlite_path = settings.sde_sqlite_path.strip()
    jumps: list[tuple[int, int]] = []
    coords: dict[int, tuple[float, float, float, str, float]] = {}

    if sqlite_path and Path(sqlite_path).is_file():
        p = Path(sqlite_path)
        jumps = _load_jumps_from_sqlite(p)
        coords = _load_coords_from_sqlite(p)
        logger.info("Loaded %s jumps from SDE sqlite", len(jumps))
    else:
        # ESI /universe/system_jumps/ is ship-jump *stats*, not stargate topology.
        logger.warning(
            "WH_INTEL_SDE_SQLITE_PATH not set; skipping bulk jump graph. "
            "Mount Fuzzwork sqlite for full map lines, or rely on per-system intel coords."
        )
        await _mark_map_graph_bootstrapped(session, "skipped")
        await session.commit()
        return

    seen: set[tuple[int, int]] = set()
    batch: list[MapJump] = []
    for a, b in jumps:
        for pair in ((a, b), (b, a)):
            if pair in seen:
                continue
            seen.add(pair)
            batch.append(MapJump(from_system_id=pair[0], to_system_id=pair[1]))
            if len(batch) >= 5000:
                session.add_all(batch)
                await session.flush()
                batch.clear()
    if batch:
        session.add_all(batch)
        await session.flush()

    if coords:
        systems: list[MapSystem] = []
        for sid, (x, y, region_id, name, sec) in coords.items():
            systems.append(
                MapSystem(
                    solar_system_id=sid,
                    name=name,
                    security=sec,
                    region_id=int(region_id),
                    x=x / 1e14,
                    y=y / 1e14,
                )
            )
            if len(systems) >= 2000:
                session.add_all(systems)
                await session.flush()
                systems.clear()
        if systems:
            session.add_all(systems)
    else:
        await _layout_from_jumps(session, jumps)

    await _mark_map_graph_bootstrapped(session, "sqlite")
    await session.commit()


async def _layout_from_jumps(session: AsyncSession, jumps: list[tuple[int, int]]) -> None:
    """Simple radial layout when SDE x/y unavailable."""
    nodes: set[int] = set()
    for a, b in jumps:
        nodes.add(a)
        nodes.add(b)
    ids = sorted(nodes)
    n = max(len(ids), 1)
    systems: list[MapSystem] = []
    for i, sid in enumerate(ids):
        angle = (2 * math.pi * i) / n
        systems.append(
            MapSystem(
                solar_system_id=sid,
                name=str(sid),
                security=0.0,
                region_id=None,
                x=math.cos(angle) * 1000,
                y=math.sin(angle) * 1000,
            )
        )
        if len(systems) >= 2000:
            session.add_all(systems)
            await session.flush()
            systems.clear()
    if systems:
        session.add_all(systems)


async def fetch_map_subset(
    session: AsyncSession,
    system_ids: set[int],
    *,
    hop: int = 1,
) -> tuple[list[MapSystem], list[MapJump]]:
    """Return systems + jumps for intel systems and N-hop neighbors."""
    if not system_ids:
        return [], []

    expanded = set(system_ids)
    frontier = set(system_ids)
    for _ in range(hop):
        if not frontier:
            break
        result = await session.execute(
            select(MapJump).where(
                (MapJump.from_system_id.in_(frontier))
                | (MapJump.to_system_id.in_(frontier))
            )
        )
        next_frontier: set[int] = set()
        jumps = list(result.scalars().all())
        for j in jumps:
            expanded.add(j.from_system_id)
            expanded.add(j.to_system_id)
            next_frontier.add(j.from_system_id)
            next_frontier.add(j.to_system_id)
        frontier = next_frontier - expanded
        expanded |= next_frontier

    sys_result = await session.execute(
        select(MapSystem).where(MapSystem.solar_system_id.in_(expanded))
    )
    systems = list(sys_result.scalars().all())

    jump_result = await session.execute(
        select(MapJump).where(
            MapJump.from_system_id.in_(expanded),
            MapJump.to_system_id.in_(expanded),
        )
    )
    return systems, list(jump_result.scalars().all())
