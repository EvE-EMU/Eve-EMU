"""Structure fuel board — ESI corp structures + hangar fuel-block counts."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.member_audit import CharacterAsset
from app.models.tools import AuthedStructure, SsoUser
from app.services.audit_scopes import parse_granted_scopes
from app.services.esi import bearer_token
from app.services.sde_search import get_type
from app.services.structure_sync import is_structure_id

logger = logging.getLogger(__name__)
_ESI = (settings.esi_base_url or "https://esi.evetech.net/latest").rstrip("/")
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; structure-fuel)"

# Common Upwell fuel block type IDs
FUEL_BLOCK_TYPE_IDS = {
    4246: "Helium Fuel Block",
    4247: "Hydrogen Fuel Block",
    4051: "Nitrogen Fuel Block",
    4312: "Oxygen Fuel Block",
}

STRUCTURE_READ_SCOPE = "esi-corporations.read_structures.v1"


def _parse_esi_dt(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        text = str(raw).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


async def _fuel_blocks_by_structure(session: AsyncSession) -> dict[int, int]:
    """Sum fuel-block quantities whose location_id is a player structure."""
    rows = (
        await session.scalars(
            select(CharacterAsset).where(CharacterAsset.type_id.in_(FUEL_BLOCK_TYPE_IDS.keys()))
        )
    ).all()
    out: dict[int, int] = {}
    seen_items: set[int] = set()
    for asset in rows:
        lid = int(asset.location_id or 0)
        if not is_structure_id(lid):
            continue
        item_id = int(asset.item_id or 0)
        if item_id in seen_items:
            continue
        seen_items.add(item_id)
        out[lid] = out.get(lid, 0) + int(asset.quantity or 0)
    return out


async def sync_corp_structure_fuel(session: AsyncSession) -> dict[str, Any]:
    """Pull fuel_expires from ESI for corps we have director/station-manager tokens for."""
    users = (await session.scalars(select(SsoUser))).all()
    by_corp: dict[int, SsoUser] = {}
    for user in users:
        scopes = parse_granted_scopes(user.scopes_json)
        if STRUCTURE_READ_SCOPE not in scopes:
            continue
        corp_id = int(user.corporation_id or 0)
        if corp_id > 0 and corp_id not in by_corp:
            by_corp[corp_id] = user

    updated = 0
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=45.0) as client:
        for corp_id, user in by_corp.items():
            token = await bearer_token(session, character_id=int(user.character_id))
            if not token:
                errors.append(f"corp {corp_id}: no token")
                continue
            headers = {"Authorization": f"Bearer {token}", "User-Agent": _UA}
            page = 1
            while page <= 20:
                resp = await client.get(
                    f"{_ESI}/corporations/{corp_id}/structures/",
                    headers=headers,
                    params={"page": page},
                )
                if resp.status_code == 403:
                    errors.append(f"corp {corp_id}: need Station Manager role")
                    break
                if resp.status_code != 200:
                    errors.append(f"corp {corp_id}: HTTP {resp.status_code}")
                    break
                rows = resp.json()
                if not isinstance(rows, list) or not rows:
                    break
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    sid = int(row.get("structure_id") or 0)
                    if not is_structure_id(sid):
                        continue
                    type_id = int(row.get("type_id") or 0)
                    type_meta = await get_type(session, type_id) if type_id else None
                    type_name = (type_meta or {}).get("name") or ""
                    system_id = int(row.get("system_id") or 0)
                    fuel_expires = _parse_esi_dt(row.get("fuel_expires"))
                    state = str(row.get("state") or "")

                    existing = await session.scalar(
                        select(AuthedStructure).where(AuthedStructure.structure_id == sid)
                    )
                    if existing:
                        existing.structure_type_id = type_id
                        existing.structure_type_name = str(type_name)[:128]
                        existing.structure_state = state[:32]
                        existing.fuel_expires_at = fuel_expires
                        existing.corporation_id = corp_id
                        if system_id:
                            existing.solar_system_id = system_id
                        if not existing.owner_character_id:
                            existing.owner_character_id = int(user.character_id)
                    else:
                        name = f"Structure {sid}"
                        # Prefer ESI universe name if we already cached it
                        from app.models.member_audit import UniverseLocation

                        loc = await session.get(UniverseLocation, sid)
                        if loc and loc.name:
                            name = loc.name
                        session.add(
                            AuthedStructure(
                                structure_id=sid,
                                structure_name=name[:256],
                                solar_system_id=system_id,
                                structure_type_id=type_id,
                                structure_type_name=str(type_name)[:128],
                                structure_state=state[:32],
                                fuel_expires_at=fuel_expires,
                                corporation_id=corp_id,
                                owner_character_id=int(user.character_id),
                            )
                        )
                    updated += 1
                if len(rows) < 1000:
                    break
                page += 1

    # Overlay fuel-block counts from asset sync
    blocks = await _fuel_blocks_by_structure(session)
    for sid, qty in blocks.items():
        row = await session.scalar(select(AuthedStructure).where(AuthedStructure.structure_id == sid))
        if row:
            row.fuel_blocks_qty = int(qty)

    await session.flush()
    return {"updated": updated, "corps": len(by_corp), "errors": errors[:10]}


async def structure_fuel_board(session: AsyncSession, *, refresh: bool = False) -> dict[str, Any]:
    if refresh:
        sync = await sync_corp_structure_fuel(session)
    else:
        sync = {"updated": 0, "corps": 0, "errors": []}

    # Always refresh block counts from assets (cheap)
    blocks = await _fuel_blocks_by_structure(session)
    for sid, qty in blocks.items():
        row = await session.scalar(select(AuthedStructure).where(AuthedStructure.structure_id == sid))
        if row:
            row.fuel_blocks_qty = int(qty)
    await session.flush()

    now = datetime.now(UTC)
    rows = (
        await session.scalars(select(AuthedStructure).order_by(AuthedStructure.structure_name))
    ).all()
    structures: list[dict[str, Any]] = []
    for r in rows:
        expires = r.fuel_expires_at
        hours_left = None
        status = "unknown"
        if expires:
            hours_left = (expires - now).total_seconds() / 3600.0
            if hours_left <= 0:
                status = "empty"
            elif hours_left < 24:
                status = "critical"
            elif hours_left < 72:
                status = "low"
            else:
                status = "ok"
        elif int(r.fuel_blocks_qty or 0) > 0:
            status = "blocks_only"
        structures.append(
            {
                "structure_id": int(r.structure_id),
                "structure_name": r.structure_name,
                "system_name": r.system_name,
                "solar_system_id": int(r.solar_system_id or 0) or None,
                "structure_type_id": int(r.structure_type_id or 0) or None,
                "structure_type_name": r.structure_type_name or "",
                "structure_state": r.structure_state or "",
                "fuel_expires_at": expires.isoformat() if expires else None,
                "hours_remaining": round(hours_left, 1) if hours_left is not None else None,
                "fuel_blocks_qty": int(r.fuel_blocks_qty or 0),
                "status": status,
                "has_market": bool(r.has_market),
                "has_reprocessing": bool(r.has_reprocessing),
                "corporation_id": int(r.corporation_id or 0) or None,
            }
        )

    structures.sort(
        key=lambda s: (
            s["hours_remaining"] is None,
            s["hours_remaining"] if s["hours_remaining"] is not None else 1e9,
            s["structure_name"].lower(),
        )
    )
    return {
        "synced_at": now.isoformat(),
        "sync": sync,
        "summary": {
            "total": len(structures),
            "critical": sum(1 for s in structures if s["status"] == "critical"),
            "low": sum(1 for s in structures if s["status"] == "low"),
            "empty": sum(1 for s in structures if s["status"] == "empty"),
            "ok": sum(1 for s in structures if s["status"] == "ok"),
        },
        "structures": structures,
        "fuel_block_types": [
            {"type_id": tid, "name": name} for tid, name in FUEL_BLOCK_TYPE_IDS.items()
        ],
    }
