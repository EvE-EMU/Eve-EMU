"""PI factory schematics from EVE Ref reference data (cached in memory)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from app.services.everef import localized_name
from app.services.everef_archive import download_reference_archive, _extract_json

logger = logging.getLogger(__name__)

# EVE type group_id → PI tier (Adam4EVE P1–P4).
_TIER_BY_GROUP: dict[int, int] = {
    1042: 1,  # Basic
    1034: 2,  # Refined
    1040: 3,  # Specialized
    1041: 4,  # Advanced
}

_cache_lock = asyncio.Lock()
_cache: list[PiSchematic] | None = None
_type_tier: dict[int, int] | None = None
_type_names: dict[int, str] | None = None


@dataclass(frozen=True)
class PiMaterial:
    type_id: int
    quantity: int


@dataclass(frozen=True)
class PiSchematic:
    schematic_id: int
    name: str
    cycle_time: int
    inputs: tuple[PiMaterial, ...]
    output_type_id: int
    output_quantity: int
    output_tier: int


def _tier_for_type(type_id: int, types_raw: dict[str, Any]) -> int:
    entry = types_raw.get(str(type_id)) or types_raw.get(type_id)
    if not isinstance(entry, dict):
        return 0
    gid = entry.get("group_id")
    try:
        return _TIER_BY_GROUP.get(int(gid), 0)
    except (TypeError, ValueError):
        return 0


async def load_pi_schematics(*, force: bool = False) -> list[PiSchematic]:
    global _cache, _type_tier, _type_names
    if _cache is not None and not force:
        return _cache

    async with _cache_lock:
        if _cache is not None and not force:
            return _cache

        logger.info("loading PI schematics from EVE Ref reference archive")
        archive = await asyncio.to_thread(download_reference_archive)
        raw_sch = _extract_json(archive, "schematics.json")
        raw_types = _extract_json(archive, "types.json")

        names: dict[int, str] = {}
        tiers: dict[int, int] = {}
        for key, entry in raw_types.items():
            if not isinstance(entry, dict):
                continue
            try:
                tid = int(entry.get("type_id") or key)
            except (TypeError, ValueError):
                continue
            label = localized_name(entry.get("name")) or f"Type {tid}"
            names[tid] = label
            tier = _tier_for_type(tid, raw_types)
            if tier:
                tiers[tid] = tier

        rows: list[PiSchematic] = []
        for entry in raw_sch.values():
            if not isinstance(entry, dict):
                continue
            try:
                sid = int(entry["schematic_id"])
                cycle = int(entry.get("cycle_time") or 3600)
            except (KeyError, TypeError, ValueError):
                continue
            products = entry.get("products") or {}
            materials = entry.get("materials") or {}
            if not products or not materials:
                continue
            prod = next(iter(products.values()))
            try:
                out_tid = int(prod["type_id"])
                out_qty = int(prod.get("quantity") or 1)
            except (KeyError, TypeError, ValueError):
                continue
            inputs: list[PiMaterial] = []
            for mat in materials.values():
                if not isinstance(mat, dict):
                    continue
                try:
                    inputs.append(
                        PiMaterial(
                            type_id=int(mat["type_id"]),
                            quantity=int(mat.get("quantity") or 1),
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            if not inputs:
                continue
            out_tier = tiers.get(out_tid) or _tier_for_type(out_tid, raw_types)
            if not out_tier:
                in_tiers = [tiers.get(i.type_id) or _tier_for_type(i.type_id, raw_types) for i in inputs]
                out_tier = max((t for t in in_tiers if t), default=0) + 1 if in_tiers else 0
            rows.append(
                PiSchematic(
                    schematic_id=sid,
                    name=localized_name(entry.get("name")) or names.get(out_tid, f"Schematic {sid}"),
                    cycle_time=max(1, cycle),
                    inputs=tuple(inputs),
                    output_type_id=out_tid,
                    output_quantity=max(1, out_qty),
                    output_tier=min(4, max(1, out_tier)) if out_tier else 1,
                )
            )

        rows.sort(key=lambda s: (s.output_tier, s.name.lower()))
        _cache = rows
        _type_tier = tiers
        _type_names = names
        logger.info("loaded %s PI schematics", len(rows))
        return rows


def pi_type_name(type_id: int) -> str:
    if _type_names and type_id in _type_names:
        return _type_names[type_id]
    return f"Type {type_id}"


def pi_type_tier(type_id: int) -> int:
    if _type_tier and type_id in _type_tier:
        return _type_tier[type_id]
    return 0


def all_pi_type_ids() -> list[int]:
    ids: set[int] = set()
    if _cache:
        for s in _cache:
            ids.add(s.output_type_id)
            for m in s.inputs:
                ids.add(m.type_id)
    if _type_tier:
        ids.update(_type_tier.keys())
    return sorted(ids)
