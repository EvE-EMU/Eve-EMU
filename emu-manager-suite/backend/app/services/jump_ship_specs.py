"""Jump-drive ship specs from Fuzzwork SDE (dogma attributes) with verified fallbacks."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.sde_import import LIGHT_YEAR_METERS

logger = logging.getLogger(__name__)

ATTR_JUMP_CONSUMPTION = 868  # jumpDriveConsumptionAmount — units per light-year
ATTR_MAX_JUMP_DISTANCE = 879  # maxJumpDistance — meters
ATTR_JUMP_FUEL_TYPE = 886  # jumpDriveConsumptionType — isotope typeID

FUEL_TYPE_NAMES: dict[int, str] = {
    16273: "Helium Isotopes",
    16274: "Hydrogen Isotopes",
    16275: "Nitrogen Isotopes",
    16276: "Oxygen Isotopes",
}

# slug, type_id, display name, category, Jump Freighters skill applies
JUMP_SHIP_REGISTRY: tuple[tuple[str, int, str, str, bool], ...] = (
    ("revelation", 19720, "Revelation", "Dreadnought", False),
    ("phoenix", 19722, "Phoenix", "Dreadnought", False),
    ("moros", 19724, "Moros", "Dreadnought", False),
    ("naglfar", 19726, "Naglfar", "Dreadnought", False),
    ("rorqual", 28659, "Rorqual", "Industrial Cap", False),
    ("archon", 23757, "Archon", "Carrier", False),
    ("nyx", 22448, "Nyx", "Supercarrier", False),
    ("avatar", 11567, "Avatar", "Titan", False),
    ("nomad", 28846, "Nomad", "Jump Freighter", True),
    ("ark", 28848, "Ark", "Jump Freighter", True),
    ("widow", 22436, "Widow", "Black Ops", False),
    ("panther", 22440, "Panther", "Black Ops", False),
)

# Verified against Tranquility SDE / EVE Ref when sqlite is unavailable.
_STATIC_SPECS: dict[int, dict[str, float | int]] = {
    19720: {"fuel_per_ly": 3000, "base_range_ly": 3.5, "fuel_type_id": 16273},
    19722: {"fuel_per_ly": 3000, "base_range_ly": 3.5, "fuel_type_id": 16275},
    19724: {"fuel_per_ly": 3000, "base_range_ly": 3.5, "fuel_type_id": 16276},
    19726: {"fuel_per_ly": 3000, "base_range_ly": 3.5, "fuel_type_id": 16274},
    28659: {"fuel_per_ly": 4000, "base_range_ly": 5.0, "fuel_type_id": 16276},
    23757: {"fuel_per_ly": 3000, "base_range_ly": 3.5, "fuel_type_id": 16273},
    22448: {"fuel_per_ly": 3000, "base_range_ly": 3.0, "fuel_type_id": 16276},
    11567: {"fuel_per_ly": 60000, "base_range_ly": 3.0, "fuel_type_id": 16273},
    28846: {"fuel_per_ly": 8200, "base_range_ly": 5.0, "fuel_type_id": 16273},
    28848: {"fuel_per_ly": 8800, "base_range_ly": 5.0, "fuel_type_id": 16275},
    22436: {"fuel_per_ly": 700, "base_range_ly": 4.0, "fuel_type_id": 16274},
    22440: {"fuel_per_ly": 700, "base_range_ly": 4.0, "fuel_type_id": 16275},
}

_cached_ships: dict[str, dict[str, Any]] | None = None


def _pick_table(conn: sqlite3.Connection, *names: str) -> str | None:
    for name in names:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND LOWER(name)=LOWER(?)",
            (name,),
        ).fetchone()
        if row:
            return str(row[0])
    return None


def _load_attrs_from_sqlite(sqlite_path: Path, type_ids: list[int]) -> dict[int, dict[int, float]]:
    conn = sqlite3.connect(str(sqlite_path))
    try:
        table = _pick_table(conn, "dgmTypeAttributes")
        if not table:
            return {}
        placeholders = ",".join("?" * len(type_ids))
        cur = conn.execute(
            f'SELECT "typeID", "attributeID", "value" FROM "{table}" '
            f'WHERE "typeID" IN ({placeholders}) AND "attributeID" IN (868, 879, 886)',
            type_ids,
        )
        out: dict[int, dict[int, float]] = {}
        for type_id, attr_id, value in cur:
            out.setdefault(int(type_id), {})[int(attr_id)] = float(value)
        return out
    finally:
        conn.close()


def _spec_for_type(type_id: int, attrs: dict[int, float]) -> dict[str, float | int]:
    fallback = _STATIC_SPECS.get(type_id, {})
    fuel_per_ly = attrs.get(ATTR_JUMP_CONSUMPTION, fallback.get("fuel_per_ly", 0))
    if attrs.get(ATTR_MAX_JUMP_DISTANCE):
        base_range_ly = attrs[ATTR_MAX_JUMP_DISTANCE] / LIGHT_YEAR_METERS
    else:
        base_range_ly = float(fallback.get("base_range_ly", 0))
    fuel_type_id = int(attrs.get(ATTR_JUMP_FUEL_TYPE, fallback.get("fuel_type_id", 16273)))
    return {
        "fuel_per_ly": float(fuel_per_ly),
        "base_range_ly": round(base_range_ly, 4),
        "fuel_type_id": fuel_type_id,
    }


def ensure_jump_ships_loaded(sqlite_path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load jump ship table once per process (SDE sqlite when present, else static SDE values)."""
    global _cached_ships
    if _cached_ships is not None:
        return _cached_ships

    path = sqlite_path or Path(settings.sde_sqlite_path)
    type_ids = [entry[1] for entry in JUMP_SHIP_REGISTRY]
    sde_attrs: dict[int, dict[int, float]] = {}
    if path.is_file():
        try:
            sde_attrs = _load_attrs_from_sqlite(path, type_ids)
            if sde_attrs:
                logger.info("EMUMS: loaded jump-drive specs from SDE sqlite (%s)", path)
        except Exception as exc:
            logger.warning("EMUMS: jump-drive SDE lookup failed (%s), using static specs", exc)

    ships: dict[str, dict[str, Any]] = {}
    for slug, type_id, name, category, is_jf in JUMP_SHIP_REGISTRY:
        spec = _spec_for_type(type_id, sde_attrs.get(type_id, {}))
        fuel_type_id = int(spec["fuel_type_id"])
        ships[slug] = {
            "slug": slug,
            "type_id": type_id,
            "name": name,
            "category": category,
            "is_jump_freighter": is_jf,
            "base_range_ly": spec["base_range_ly"],
            "fuel_per_ly": spec["fuel_per_ly"],
            "fuel_type_id": fuel_type_id,
            "fuel_type": FUEL_TYPE_NAMES.get(fuel_type_id, f"Type {fuel_type_id}"),
            "source": "sde" if type_id in sde_attrs else "static",
        }

    _cached_ships = ships
    return ships


def get_jump_ship(slug: str) -> dict[str, Any] | None:
    return ensure_jump_ships_loaded().get(slug)


def list_jump_ship_specs() -> list[dict[str, Any]]:
    ships = ensure_jump_ships_loaded()
    return [
        {
            "slug": s["slug"],
            "name": s["name"],
            "category": s["category"],
            "is_jump_freighter": s["is_jump_freighter"],
            "base_range_ly": s["base_range_ly"],
            "fuel_per_ly": s["fuel_per_ly"],
            "fuel_type": s["fuel_type"],
            "fuel_type_id": s["fuel_type_id"],
        }
        for s in ships.values()
    ]
