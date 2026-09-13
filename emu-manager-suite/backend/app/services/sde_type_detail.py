"""Detailed SDE type information — ESI dogma + optional Fuzzwork industry data."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import SdeTypeIndex
from app.services.storefront import storefront_listing_for_type
from app.services.esi import esi_get
from app.services.sde_search import get_type

logger = logging.getLogger(__name__)

_SKILL_PAIRS = (
    (182, 277),
    (183, 278),
    (184, 279),
    (1285, 1286),
    (1289, 1287),
    (1290, 1288),
)

_ACTIVITY_NAMES = {
    1: "Manufacturing",
    3: "Time Efficiency Research",
    4: "Material Efficiency Research",
    5: "Copying",
    7: "Reverse Engineering",
    8: "Invention",
    11: "Reaction",
}

_attr_cache: dict[int, dict] = {}


def _pick_table(conn: sqlite3.Connection, *names: str) -> str | None:
    for name in names:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND LOWER(name)=LOWER(?)",
            (name,),
        ).fetchone()
        if row:
            return str(row[0])
    return None


async def _resolve_attribute(attr_id: int) -> dict:
    if attr_id in _attr_cache:
        return _attr_cache[attr_id]
    status, body = await esi_get(f"/dogma/attributes/{attr_id}/")
    if status == 200 and isinstance(body, dict):
        info = {
            "attribute_id": attr_id,
            "name": str(body.get("name") or f"attr_{attr_id}"),
            "display_name": str(body.get("display_name") or body.get("name") or f"Attribute {attr_id}"),
            "description": str(body.get("description") or ""),
        }
    else:
        info = {
            "attribute_id": attr_id,
            "name": f"attr_{attr_id}",
            "display_name": f"Attribute {attr_id}",
            "description": "",
        }
    _attr_cache[attr_id] = info
    return info


async def _resolve_skill_name(skill_type_id: int) -> str:
    status, body = await esi_get(f"/universe/types/{skill_type_id}/")
    if status == 200 and isinstance(body, dict):
        return str(body.get("name") or f"Skill {skill_type_id}")
    return f"Skill {skill_type_id}"


def _industry_from_sqlite(type_id: int, sqlite_path: Path) -> list[dict]:
    if not sqlite_path.is_file():
        return []
    conn = sqlite3.connect(str(sqlite_path))
    try:
        products_table = _pick_table(conn, "industryActivityProducts")
        materials_table = _pick_table(conn, "industryActivityMaterials")
        types_table = _pick_table(conn, "invTypes")
        if not products_table or not materials_table or not types_table:
            return []

        type_names: dict[int, str] = {}
        cur = conn.execute(f'SELECT "typeID", "typeName" FROM "{types_table}"')
        for tid, name in cur.fetchall():
            type_names[int(tid)] = str(name or "")

        recipes: list[dict] = []
        prod_cur = conn.execute(
            f'SELECT "typeID", "activityID", "productTypeID", "quantity" '
            f'FROM "{products_table}" WHERE "productTypeID" = ?',
            (type_id,),
        )
        for blueprint_id, activity_id, _product_id, product_qty in prod_cur.fetchall():
            activity_id = int(activity_id)
            blueprint_id = int(blueprint_id)
            mat_cur = conn.execute(
                f'SELECT "materialTypeID", "quantity" FROM "{materials_table}" '
                f'WHERE "typeID" = ? AND "activityID" = ?',
                (blueprint_id, activity_id),
            )
            materials = [
                {
                    "type_id": int(mid),
                    "name": type_names.get(int(mid), f"Type {mid}"),
                    "quantity": int(qty),
                }
                for mid, qty in mat_cur.fetchall()
            ]
            recipes.append(
                {
                    "activity": _ACTIVITY_NAMES.get(activity_id, f"Activity {activity_id}"),
                    "blueprint_type_id": blueprint_id,
                    "blueprint_name": type_names.get(blueprint_id, f"Blueprint {blueprint_id}"),
                    "product_quantity": int(product_qty),
                    "materials": materials,
                }
            )
        return recipes
    except Exception as exc:
        logger.warning("SDE industry lookup failed for type %s: %s", type_id, exc)
        return []
    finally:
        conn.close()


async def get_type_detail(session: AsyncSession, type_id: int) -> dict | None:
    """Assemble rich type detail from local index, ESI, SDE sqlite, and storefront."""
    local = await get_type(session, type_id)

    status, esi_type = await esi_get(f"/universe/types/{type_id}/")
    if status != 200 or not isinstance(esi_type, dict):
        if not local:
            return None
        esi_type = {}

    name = str(esi_type.get("name") or (local or {}).get("name") or f"Type {type_id}")
    description = str(esi_type.get("description") or "").replace("\r\n", "\n").strip()
    group_id = esi_type.get("group_id")
    published = bool(esi_type.get("published", True))
    mass = float(esi_type.get("mass") or 0)
    volume = float(esi_type.get("volume") or (local or {}).get("volume_m3") or 0)
    capacity = float(esi_type.get("capacity") or 0)

    raw_attrs = esi_type.get("dogma_attributes") or []
    attr_values: dict[int, float] = {}
    for entry in raw_attrs:
        if isinstance(entry, dict):
            attr_values[int(entry.get("attribute_id") or 0)] = float(entry.get("value") or 0)

    attributes: list[dict] = []
    skill_attr_ids = {aid for pair in _SKILL_PAIRS for aid in pair}
    for attr_id, value in attr_values.items():
        if value == 0 or attr_id in skill_attr_ids:
            continue
        meta = await _resolve_attribute(attr_id)
        attributes.append(
            {
                "attribute_id": attr_id,
                "name": meta["display_name"],
                "value": value,
                "description": meta["description"],
            }
        )
    attributes.sort(key=lambda a: a["name"].lower())

    requirements: list[dict] = []
    for skill_attr, level_attr in _SKILL_PAIRS:
        skill_type_id = int(attr_values.get(skill_attr) or 0)
        if skill_type_id <= 0:
            continue
        skill_name = await _resolve_skill_name(skill_type_id)
        level = int(attr_values.get(level_attr) or 1)
        requirements.append(
            {"kind": "skill", "type_id": skill_type_id, "name": skill_name, "level": level}
        )

    sqlite_path = Path(settings.sde_sqlite_path)
    industry = _industry_from_sqlite(type_id, sqlite_path)

    listing = await storefront_listing_for_type(session, type_id)
    storefront_out = None
    if listing:
        storefront_out = {
            "id": listing.get("type_id"),
            "type_id": listing.get("type_id"),
            "type_name": listing.get("name"),
            "quantity": listing.get("quantity"),
            "price_public_isk": listing.get("unit_price_isk"),
            "suggested_price_isk": listing.get("janice_split_isk") or listing.get("unit_price_isk"),
        }

    return {
        "type_id": type_id,
        "name": name,
        "group_name": (local or {}).get("group_name") or "",
        "category_name": (local or {}).get("category_name") or "",
        "group_id": group_id,
        "description": description,
        "published": published,
        "mass": mass,
        "volume_m3": volume,
        "capacity": capacity,
        "base_price": float((local or {}).get("base_price") or 0),
        "attributes": attributes,
        "requirements": requirements,
        "industry": industry,
        "storefront_listing": storefront_out,
        "skill_meta": await _skill_meta(type_id, attr_values) if _is_skill_category(local, esi_type) else None,
    }


def _is_skill_category(local: dict | None, esi_type: dict) -> bool:
    cat = (local or {}).get("category_name") or ""
    if "skill" in cat.lower():
        return True
    return str(esi_type.get("name") or "").endswith(" Skill")


async def _skill_meta(type_id: int, attr_values: dict[int, float]) -> dict:
    rank = int(attr_values.get(275) or 0)
    primary = int(attr_values.get(180) or 0)
    secondary = int(attr_values.get(181) or 0)
    attr_names = {}
    for aid in (primary, secondary):
        if aid > 0:
            meta = await _resolve_attribute(aid)
            attr_names[aid] = meta["display_name"]
    return {
        "rank": rank,
        "primary_attribute": attr_names.get(primary, ""),
        "secondary_attribute": attr_names.get(secondary, ""),
        "can_not_be_trained": bool(attr_values.get(277)),  # often paired; informational
    }


async def get_skill_requirements_for_type(session: AsyncSession, type_id: int) -> list[dict]:
    """Lightweight skill requirements for batch checks."""
    status, esi_type = await esi_get(f"/universe/types/{type_id}/")
    if status != 200 or not isinstance(esi_type, dict):
        return []
    attr_values: dict[int, float] = {}
    for entry in esi_type.get("dogma_attributes") or []:
        if isinstance(entry, dict):
            attr_values[int(entry.get("attribute_id") or 0)] = float(entry.get("value") or 0)
    requirements: list[dict] = []
    for skill_attr, level_attr in _SKILL_PAIRS:
        skill_type_id = int(attr_values.get(skill_attr) or 0)
        if skill_type_id <= 0:
            continue
        skill_name = await _resolve_skill_name(skill_type_id)
        level = int(attr_values.get(level_attr) or 1)
        requirements.append({"kind": "skill", "type_id": skill_type_id, "name": skill_name, "level": level})
    return requirements
