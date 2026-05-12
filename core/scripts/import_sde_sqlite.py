#!/usr/bin/env python3
"""
Load SDE from a Fuzzwork-style EVE SQLite dump into Postgres (``sde_*`` tables).

Typical source (download and decompress first):
  https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2

Usage (from ``core/`` directory):

  set PYTHONPATH=.
  set CORE_DATABASE_URL=postgresql+asyncpg://eve:eve@localhost:5432/eve_emu_core
  python scripts/import_sde_sqlite.py --sqlite path\\to\\sqlite-latest.sqlite

By default existing ``sde_*`` rows are **truncated** before import (see ``--no-replace``).
"""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.sde.models import SdeInvGroup, SdeMapSolarSystem, SdeType


def _pick_table(conn: sqlite3.Connection, *names: str) -> str:
    for n in names:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND LOWER(name)=LOWER(?)",
            (n,),
        ).fetchone()
        if row:
            return str(row[0])
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    all_names = [r[0] for r in cur.fetchall()]
    raise RuntimeError(f"None of {names!r} found. Sample tables: {all_names[:50]}")


async def _clear_sde(session: AsyncSession) -> None:
    await session.execute(delete(SdeType))
    await session.execute(delete(SdeMapSolarSystem))
    await session.execute(delete(SdeInvGroup))


def _bool(v: object) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    try:
        return int(v) != 0
    except (TypeError, ValueError):
        return False


async def _import_groups(session: AsyncSession, conn: sqlite3.Connection) -> int:
    t = _pick_table(conn, "invGroups")
    cur = conn.execute(f'SELECT "groupID", "categoryID", "groupName" FROM "{t}"')
    n = 0
    batch: list[SdeInvGroup] = []
    for row in cur:
        batch.append(
            SdeInvGroup(group_id=int(row[0]), category_id=int(row[1]), name=str(row[2] or ""))
        )
        if len(batch) >= 2000:
            session.add_all(batch)
            await session.flush()
            n += len(batch)
            batch.clear()
    if batch:
        session.add_all(batch)
        await session.flush()
        n += len(batch)
    return n


async def _import_types(session: AsyncSession, conn: sqlite3.Connection) -> int:
    t = _pick_table(conn, "invTypes")
    cur = conn.execute(
        f'SELECT "typeID", "groupID", "typeName", "description", "mass", "volume", '
        f'"portionSize", "published" FROM "{t}"'
    )
    n = 0
    batch: list[SdeType] = []
    for row in cur:
        batch.append(
            SdeType(
                type_id=int(row[0]),
                group_id=int(row[1]),
                name=str(row[2] or ""),
                description=str(row[3]) if row[3] is not None else None,
                mass=float(row[4]) if row[4] is not None else None,
                volume=float(row[5]) if row[5] is not None else None,
                portion_size=int(row[6]) if row[6] is not None else None,
                published=_bool(row[7]),
            )
        )
        if len(batch) >= 2000:
            session.add_all(batch)
            await session.flush()
            n += len(batch)
            batch.clear()
    if batch:
        session.add_all(batch)
        await session.flush()
        n += len(batch)
    return n


async def _import_systems(session: AsyncSession, conn: sqlite3.Connection) -> int:
    t = _pick_table(conn, "mapSolarSystems")
    cur = conn.execute(
        f'SELECT "solarSystemID", "solarSystemName", "security", '
        f'"constellationID", "regionID" FROM "{t}"'
    )
    n = 0
    batch: list[SdeMapSolarSystem] = []
    for row in cur:
        sec = row[2]
        batch.append(
            SdeMapSolarSystem(
                solar_system_id=int(row[0]),
                name=str(row[1] or ""),
                security=float(sec) if sec is not None else 0.0,
                constellation_id=int(row[3]),
                region_id=int(row[4]),
            )
        )
        if len(batch) >= 2000:
            session.add_all(batch)
            await session.flush()
            n += len(batch)
            batch.clear()
    if batch:
        session.add_all(batch)
        await session.flush()
        n += len(batch)
    return n


async def main_async(*, sqlite_path: Path, database_url: str, replace: bool) -> None:
    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    conn = sqlite3.connect(str(sqlite_path))
    try:
        async with factory() as session:
            if replace:
                await _clear_sde(session)
            g = await _import_groups(session, conn)
            ty = await _import_types(session, conn)
            sy = await _import_systems(session, conn)
            await session.commit()
            print(f"Imported invGroups={g}, invTypes={ty}, mapSolarSystems={sy}")
    finally:
        conn.close()
        await engine.dispose()


def main() -> None:
    p = argparse.ArgumentParser(description="Import Fuzzwork EVE SQLite SDE into Postgres.")
    p.add_argument("--sqlite", type=Path, required=True, help="Path to sqlite-latest.sqlite")
    p.add_argument(
        "--database-url",
        type=str,
        default="",
        help="postgresql+asyncpg://... (default: env CORE_DATABASE_URL)",
    )
    p.add_argument(
        "--no-replace",
        dest="replace",
        action="store_false",
        help="Do not truncate sde_* tables first (fails if rows already exist)",
    )
    p.set_defaults(replace=True)
    args = p.parse_args()
    if not args.sqlite.is_file():
        raise SystemExit(f"SQLite file not found: {args.sqlite}")

    import os

    url = args.database_url.strip() or os.environ.get("CORE_DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("Set --database-url or CORE_DATABASE_URL")

    asyncio.run(main_async(sqlite_path=args.sqlite, database_url=url, replace=args.replace))


if __name__ == "__main__":
    main()
