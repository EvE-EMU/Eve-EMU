"""SDE industry recipes — blueprints, materials, job times from Fuzzwork SQLite."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

MANUFACTURING = 1

_ACTIVITY_NAMES = {
    1: "Manufacturing",
    3: "Time Efficiency Research",
    4: "Material Efficiency Research",
    5: "Copying",
    8: "Invention",
    11: "Reaction",
}


@dataclass
class RecipeMaterial:
    type_id: int
    name: str
    quantity: int


@dataclass
class IndustryRecipe:
    blueprint_type_id: int
    blueprint_name: str
    product_type_id: int
    product_name: str
    product_quantity: int
    activity_id: int
    activity_name: str
    time_seconds: int
    materials: list[RecipeMaterial] = field(default_factory=list)


def _sqlite_path() -> Path:
    return Path(settings.sde_sqlite_path)


def _pick_table(conn: sqlite3.Connection, *names: str) -> str | None:
    for name in names:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND LOWER(name)=LOWER(?)",
            (name,),
        ).fetchone()
        if row:
            return str(row[0])
    return None


@lru_cache(maxsize=1)
def _type_names_map() -> dict[int, str]:
    path = _sqlite_path()
    if not path.is_file():
        return {}
    conn = sqlite3.connect(str(path))
    try:
        types_table = _pick_table(conn, "invTypes")
        if not types_table:
            return {}
        cur = conn.execute(f'SELECT "typeID", "typeName" FROM "{types_table}"')
        return {int(tid): str(name or "") for tid, name in cur.fetchall()}
    finally:
        conn.close()


def type_name(type_id: int) -> str:
    return _type_names_map().get(type_id, f"Type {type_id}")


def blueprint_for_product(product_type_id: int, *, activity_id: int = MANUFACTURING) -> IndustryRecipe | None:
    """Find the manufacturing blueprint that produces product_type_id."""
    path = _sqlite_path()
    if not path.is_file():
        return None
    conn = sqlite3.connect(str(path))
    try:
        products_table = _pick_table(conn, "industryActivityProducts")
        materials_table = _pick_table(conn, "industryActivityMaterials")
        activity_table = _pick_table(conn, "industryActivity")
        if not products_table or not materials_table:
            return None
        row = conn.execute(
            f'SELECT "typeID", "quantity" FROM "{products_table}" '
            f'WHERE "productTypeID" = ? AND "activityID" = ? LIMIT 1',
            (product_type_id, activity_id),
        ).fetchone()
        if not row:
            return None
        blueprint_id, product_qty = int(row[0]), int(row[1])
        return _recipe_from_blueprint(conn, blueprint_id, activity_id, product_qty, materials_table, activity_table)
    finally:
        conn.close()


def recipe_for_blueprint(blueprint_type_id: int, *, activity_id: int = MANUFACTURING) -> IndustryRecipe | None:
    path = _sqlite_path()
    if not path.is_file():
        return None
    conn = sqlite3.connect(str(path))
    try:
        products_table = _pick_table(conn, "industryActivityProducts")
        materials_table = _pick_table(conn, "industryActivityMaterials")
        activity_table = _pick_table(conn, "industryActivity")
        if not products_table or not materials_table:
            return None
        row = conn.execute(
            f'SELECT "productTypeID", "quantity" FROM "{products_table}" '
            f'WHERE "typeID" = ? AND "activityID" = ? LIMIT 1',
            (blueprint_type_id, activity_id),
        ).fetchone()
        if not row:
            return None
        product_id, product_qty = int(row[0]), int(row[1])
        return _recipe_from_blueprint(
            conn, blueprint_type_id, activity_id, product_qty, materials_table, activity_table, product_id
        )
    finally:
        conn.close()


def _recipe_from_blueprint(
    conn: sqlite3.Connection,
    blueprint_id: int,
    activity_id: int,
    product_qty: int,
    materials_table: str,
    activity_table: str | None,
    product_type_id: int | None = None,
) -> IndustryRecipe | None:
    names = _type_names_map()
    if product_type_id is None:
        prod = conn.execute(
            f'SELECT "productTypeID" FROM industryActivityProducts WHERE "typeID"=? AND "activityID"=?',
            (blueprint_id, activity_id),
        ).fetchone()
        product_type_id = int(prod[0]) if prod else 0
    mat_cur = conn.execute(
        f'SELECT "materialTypeID", "quantity" FROM "{materials_table}" '
        f'WHERE "typeID" = ? AND "activityID" = ?',
        (blueprint_id, activity_id),
    )
    materials = [
        RecipeMaterial(type_id=int(mid), name=names.get(int(mid), f"Type {mid}"), quantity=int(qty))
        for mid, qty in mat_cur.fetchall()
    ]
    time_seconds = 3600
    if activity_table:
        trow = conn.execute(
            f'SELECT "time" FROM "{activity_table}" WHERE "typeID"=? AND "activityID"=?',
            (blueprint_id, activity_id),
        ).fetchone()
        if trow:
            time_seconds = int(trow[0] or 3600)
    return IndustryRecipe(
        blueprint_type_id=blueprint_id,
        blueprint_name=names.get(blueprint_id, f"Blueprint {blueprint_id}"),
        product_type_id=int(product_type_id or 0),
        product_name=names.get(int(product_type_id or 0), f"Type {product_type_id}"),
        product_quantity=product_qty,
        activity_id=activity_id,
        activity_name=_ACTIVITY_NAMES.get(activity_id, f"Activity {activity_id}"),
        time_seconds=time_seconds,
        materials=materials,
    )


def has_manufacturing_recipe(type_id: int) -> bool:
    return blueprint_for_product(type_id) is not None


def apply_me(materials: list[RecipeMaterial], me: int, *, structure_bonus_pct: float = 0) -> list[RecipeMaterial]:
    """Apply material efficiency and structure material bonus."""
    import math

    me_factor = max(0.0, 1.0 - min(me, 10) * 0.01)
    struct_factor = max(0.0, 1.0 - structure_bonus_pct / 100.0)
    out: list[RecipeMaterial] = []
    for mat in materials:
        qty = math.ceil(mat.quantity * me_factor * struct_factor)
        qty = max(1, qty) if mat.quantity > 0 else 0
        out.append(RecipeMaterial(type_id=mat.type_id, name=mat.name, quantity=qty))
    return out
