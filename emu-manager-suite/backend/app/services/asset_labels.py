"""Asset type/flag display labels and ESI type name fallback."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tools import SdeTypeIndex

logger = logging.getLogger(__name__)
_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; audit)"

# Known gaps in local SDE index or special display cases.
TYPE_NAME_OVERRIDES: dict[int, str] = {
    34562: "Plastic Wrap",
}

FLAG_LABELS: dict[str, str] = {
    "ContainerAssetSafety": "Asset Safety",
    "AssetSafety": "Asset Safety",
    "Hangar": "Hangar",
    "Cargo": "Cargo",
    "DroneBay": "Drone Bay",
    "ShipHangar": "Ship Hangar",
    "FleetHangar": "Fleet Hangar",
    "CorpSAG1": "Corp Hangar Division 1",
    "CorpSAG2": "Corp Hangar Division 2",
    "CorpSAG3": "Corp Hangar Division 3",
    "CorpSAG4": "Corp Hangar Division 4",
    "CorpSAG5": "Corp Hangar Division 5",
    "CorpSAG6": "Corp Hangar Division 6",
    "CorpSAG7": "Corp Hangar Division 7",
}


def flag_label(flag: str) -> str:
    text = (flag or "").strip()
    if not text:
        return ""
    return FLAG_LABELS.get(text, text)


def resolve_type_name(type_id: int, sde_name: str | None = None, *, flag: str = "") -> str:
    tid = int(type_id or 0)
    if tid <= 0:
        if flag == "ContainerAssetSafety":
            return "Asset Safety Wrapper"
        return "Unknown"
    if tid in TYPE_NAME_OVERRIDES:
        return TYPE_NAME_OVERRIDES[tid]
    name = (sde_name or "").strip()
    if name and not name.startswith("Type "):
        return name
    if flag == "ContainerAssetSafety":
        return "Asset Safety Wrapper"
    if name:
        return name
    return f"Type {tid}"


def asset_display_name(
    *,
    type_id: int,
    type_name: str,
    custom_name: str = "",
    flag: str = "",
) -> str:
    base = resolve_type_name(type_id, type_name, flag=flag)
    custom = (custom_name or "").strip()
    if custom and custom.lower() != base.lower():
        return f"{custom} ({base})"
    return base


async def load_type_names(session: AsyncSession, type_ids: set[int]) -> dict[int, str]:
    if not type_ids:
        return {}
    rows = await session.scalars(select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(type_ids)))
    out = {int(r.type_id): r.name for r in rows.all()}
    missing = {tid for tid in type_ids if tid > 0 and tid not in out}
    if missing:
        esi = await fetch_esi_type_names(missing)
        out.update(esi)
    return out


async def fetch_esi_type_names(type_ids: set[int]) -> dict[int, str]:
    names: dict[int, str] = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for tid in sorted(type_ids):
            try:
                resp = await client.get(
                    f"{_ESI}/universe/types/{tid}/",
                    headers={"Accept": "application/json", "User-Agent": _UA},
                )
                if resp.status_code != 200:
                    continue
                body: Any = resp.json()
                if isinstance(body, dict) and body.get("name"):
                    names[tid] = str(body["name"])
            except Exception:
                logger.debug("ESI type lookup failed for %s", tid)
    return names
