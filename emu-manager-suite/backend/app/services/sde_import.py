"""Import EVE SDE (map + type index) from Fuzzwork SQLite."""

from __future__ import annotations

import logging
import sqlite3
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SdeStargateLink, SdeSystem, SdeTypeIndex

logger = logging.getLogger(__name__)

# EVE stores positions in meters; jump ranges are quoted in light-years.
LIGHT_YEAR_METERS = 9.460528405e15


def _pick_table(conn: sqlite3.Connection, *names: str) -> str:
    for name in names:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND LOWER(name)=LOWER(?)",
            (name,),
        ).fetchone()
        if row:
            return str(row[0])
    raise RuntimeError(f"SDE table not found: {names}")


def _load_region_names(conn: sqlite3.Connection) -> dict[int, str]:
    table = _pick_table(conn, "mapRegions")
    cur = conn.execute(f'SELECT "regionID", "regionName" FROM "{table}"')
    return {int(r[0]): str(r[1] or "") for r in cur}


def _load_constellation_names(conn: sqlite3.Connection) -> dict[int, str]:
    table = _pick_table(conn, "mapConstellations")
    cur = conn.execute(f'SELECT "constellationID", "constellationName" FROM "{table}"')
    return {int(r[0]): str(r[1] or "") for r in cur}


async def sde_map_is_loaded(session: AsyncSession) -> bool:
    count = await session.scalar(
        select(func.count()).select_from(SdeSystem).where(SdeSystem.x.isnot(None))
    )
    return bool(count and count >= 8000)


async def import_sde_map_from_sqlite(session: AsyncSession, sqlite_path: Path) -> dict[str, int]:
    """Replace map tables with full SDE import from Fuzzwork SQLite."""
    path = Path(sqlite_path)
    if not path.is_file():
        raise FileNotFoundError(f"SDE sqlite not found: {path}")

    conn = sqlite3.connect(str(path))
    try:
        regions = _load_region_names(conn)
        constellations = _load_constellation_names(conn)
        systems_table = _pick_table(conn, "mapSolarSystems")
        jumps_table = _pick_table(conn, "mapSolarSystemJumps")

        cur = conn.execute(
            f'SELECT "solarSystemID", "solarSystemName", "security", '
            f'"regionID", "constellationID", "x", "y", "z" FROM "{systems_table}"'
        )
        system_rows = cur.fetchall()

        jump_cur = conn.execute(
            f'SELECT "fromSolarSystemID", "toSolarSystemID" FROM "{jumps_table}"'
        )
        jump_rows = jump_cur.fetchall()
    finally:
        conn.close()

    await session.execute(delete(SdeStargateLink))
    await session.execute(delete(SdeSystem))
    await session.flush()

    systems: list[SdeSystem] = []
    for row in system_rows:
        sid = int(row[0])
        region_id = int(row[3]) if row[3] is not None else None
        constellation_id = int(row[4]) if row[4] is not None else None
        systems.append(
            SdeSystem(
                system_id=sid,
                name=str(row[1] or ""),
                security=float(row[2] or 0.0),
                region_id=region_id,
                constellation_id=constellation_id,
                region_name=regions.get(region_id, "") if region_id else "",
                constellation_name=constellations.get(constellation_id, "") if constellation_id else "",
                x=float(row[5]) if row[5] is not None else None,
                y=float(row[6]) if row[6] is not None else None,
                z=float(row[7]) if row[7] is not None else None,
            )
        )
        if len(systems) >= 2000:
            session.add_all(systems)
            await session.flush()
            systems.clear()
    if systems:
        session.add_all(systems)
        await session.flush()

    links: list[SdeStargateLink] = []
    seen: set[tuple[int, int]] = set()
    for a, b in jump_rows:
        pair = (int(a), int(b))
        if pair in seen:
            continue
        seen.add(pair)
        links.append(SdeStargateLink(from_system_id=pair[0], to_system_id=pair[1]))
        if len(links) >= 5000:
            session.add_all(links)
            await session.flush()
            links.clear()
    if links:
        session.add_all(links)
        await session.flush()

    stats = {
        "systems": len(system_rows),
        "stargate_links": len(seen),
    }
    logger.info("EMUMS: imported SDE map — %s systems, %s stargate links", stats["systems"], stats["stargate_links"])
    from app.services.map_layout import apply_map_layout

    await apply_map_layout(session)
    return stats


async def ensure_sde_map(session: AsyncSession, sqlite_path: Path | None) -> bool:
    """Import SDE map when coordinates are missing from the database."""
    if await sde_map_is_loaded(session):
        return False
    if not sqlite_path or not sqlite_path.is_file():
        logger.warning("EMUMS: SDE map not loaded — set EMUMS_SDE_SQLITE_PATH to Fuzzwork latest-sqlite.db")
        return False
    await import_sde_map_from_sqlite(session, sqlite_path)
    return True


# Full published-type import is ~27k rows; demo seed is only ~60.
_MIN_SDE_TYPES_LOADED = 10_000


async def sde_types_is_loaded(session: AsyncSession) -> bool:
    count = await session.scalar(select(func.count()).select_from(SdeTypeIndex))
    return bool(count and count >= _MIN_SDE_TYPES_LOADED)


async def import_sde_types_from_sqlite(session: AsyncSession, sqlite_path: Path) -> dict[str, int]:
    """Replace emums_sde_types with all published invTypes from Fuzzwork SQLite."""
    path = Path(sqlite_path)
    if not path.is_file():
        raise FileNotFoundError(f"SDE sqlite not found: {path}")

    conn = sqlite3.connect(str(path))
    try:
        types_table = _pick_table(conn, "invTypes")
        groups_table = _pick_table(conn, "invGroups")
        categories_table = _pick_table(conn, "invCategories")
        cur = conn.execute(
            f'SELECT t."typeID", t."typeName", g."groupName", c."categoryName", '
            f't."volume", t."basePrice" '
            f'FROM "{types_table}" t '
            f'LEFT JOIN "{groups_table}" g ON t."groupID" = g."groupID" '
            f'LEFT JOIN "{categories_table}" c ON g."categoryID" = c."categoryID" '
            f'WHERE t."published" = 1 AND t."typeID" > 0'
        )
        type_rows = cur.fetchall()
    finally:
        conn.close()

    await session.execute(delete(SdeTypeIndex))
    await session.flush()

    batch: list[SdeTypeIndex] = []
    for row in type_rows:
        type_id = int(row[0])
        name = str(row[1] or "").strip()
        if not name or name.startswith("#"):
            continue
        batch.append(
            SdeTypeIndex(
                type_id=type_id,
                name=name,
                group_name=str(row[2] or ""),
                category_name=str(row[3] or ""),
                volume_m3=float(row[4] or 0),
                base_price=Decimal(str(row[5] or 0)),
            )
        )
        if len(batch) >= 2000:
            session.add_all(batch)
            await session.flush()
            batch.clear()
    if batch:
        session.add_all(batch)
        await session.flush()

    stats = {"types": len(type_rows)}
    logger.info("EMUMS: imported SDE types — %s published types", stats["types"])
    return stats


async def ensure_sde_types(session: AsyncSession, sqlite_path: Path | None) -> bool:
    """Import full published type index when only demo rows are present."""
    if await sde_types_is_loaded(session):
        return False
    if not sqlite_path or not sqlite_path.is_file():
        logger.warning("EMUMS: SDE types not loaded — set EMUMS_SDE_SQLITE_PATH to Fuzzwork latest-sqlite.db")
        return False
    await import_sde_types_from_sqlite(session, sqlite_path)
    return True
