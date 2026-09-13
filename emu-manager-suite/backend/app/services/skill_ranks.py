"""Skill rank (dogma attribute 275) from Fuzzwork SDE SQLite."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

ATTR_SKILL_RANK = 275
_cached_ranks: dict[int, int] | None = None


def _pick_table(conn: sqlite3.Connection, *names: str) -> str | None:
    for name in names:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND LOWER(name)=LOWER(?)",
            (name,),
        ).fetchone()
        if row:
            return str(row[0])
    return None


def load_skill_ranks(type_ids: list[int]) -> dict[int, int]:
    """Return skill rank per type_id (defaults to 1 when unknown)."""
    global _cached_ranks
    if not type_ids:
        return {}

    sqlite_path = Path(settings.sde_sqlite_path)
    if not sqlite_path.is_file():
        return {tid: 1 for tid in type_ids}

    if _cached_ranks is None:
        _cached_ranks = {}
        try:
            conn = sqlite3.connect(str(sqlite_path))
            try:
                table = _pick_table(conn, "dgmTypeAttributes")
                if not table:
                    return {tid: 1 for tid in type_ids}
                cur = conn.execute(
                    f'SELECT "typeID", "valueInt", "valueFloat" FROM "{table}" WHERE "attributeID" = ?',
                    (ATTR_SKILL_RANK,),
                )
                for type_id, value_int, value_float in cur.fetchall():
                    raw = value_int if value_int is not None else value_float
                    rank = int(float(raw or 0))
                    if rank > 0:
                        _cached_ranks[int(type_id)] = rank
            finally:
                conn.close()
        except Exception:
            logger.exception("skill_ranks: failed to read SDE sqlite")
            _cached_ranks = {}

    return {tid: _cached_ranks.get(tid, 1) for tid in type_ids}
