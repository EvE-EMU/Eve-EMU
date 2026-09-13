"""Sync in-game ship fittings and blueprints from ESI into industry planning tables."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tools import FittingRecord, IndyBlueprint, IndyJobRecord, SsoUser
from app.services.asset_labels import load_type_names
from app.services.audit_scopes import has_blueprints_access, has_fittings_access, parse_granted_scopes
from app.services.esi import bearer_token, resolve_universe_names
from app.services.location_display import resolve_location_labels

logger = logging.getLogger(__name__)
_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; industry-sync)"
_EFT_MAX_LEN = 60_000

# ESI fitting flags that are not ship module slots (cargo, drones, etc.)
_NON_FIT_FLAG_NAMES = frozenset(
    {
        "Cargo",
        "FleetHangar",
        "ShipHangar",
        "DroneBay",
        "Hangar",
        "StructureDeck",
        "Locked",
        "Unlocked",
        "CargoHold",
        "SpecializedFuelBay",
        "SecondaryStorage",
        "FrigateEscapeBay",
        "QuafeBay",
        "FighterBay",
        "FighterTube0",
        "FighterTube1",
        "FighterTube2",
        "FighterTube3",
        "FighterTube4",
        "Module",
    }
)


def _is_fitted_item(item: dict[str, Any]) -> bool:
    flag = item.get("flag")
    if isinstance(flag, str):
        if flag in _NON_FIT_FLAG_NAMES:
            return False
        if "Slot" in flag or flag.startswith(("Hi", "Med", "Lo", "Rig", "Sub", "Service")):
            return True
        return False
    try:
        f = int(flag)
    except (TypeError, ValueError):
        return False
    if f in {5, 87}:  # Cargo, DroneBay
        return False
    if 11 <= f <= 34:  # hi / med / lo slots
        return True
    if 92 <= f <= 94:  # rigs
        return True
    if 125 <= f <= 128:  # subsystems
        return True
    if 131 <= f <= 134:  # service slots
        return True
    if 177 <= f <= 179:  # fighter tubes
        return True
    return False


def _fitted_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [i for i in items if isinstance(i, dict) and _is_fitted_item(i)]


def _module_type_ids(items: list[dict[str, Any]]) -> list[int]:
    ids: list[int] = []
    for item in _fitted_items(items):
        tid = int(item.get("type_id") or 0)
        if tid > 0:
            ids.append(tid)
    return ids


def _build_eft(ship_name: str, items: list[dict[str, Any]], type_names: dict[int, str]) -> str:
    lines = [ship_name or "Unknown Ship", ""]
    for item in _fitted_items(items):
        tid = int(item.get("type_id") or 0)
        qty = int(item.get("quantity") or 1)
        name = type_names.get(tid, f"Type {tid}")
        if qty > 1:
            lines.append(f"{name} x{qty}")
        else:
            lines.append(name)
    text = "\n".join(lines).strip()
    if len(text) > _EFT_MAX_LEN:
        text = text[: _EFT_MAX_LEN - 20] + "\n… [truncated]"
    return text


async def sync_character_fittings(
    session: AsyncSession,
    character_id: int,
    *,
    granted: set[str] | None = None,
    scope_errors: dict[str, str] | None = None,
) -> int:
    """Pull saved ship fittings from ESI for one character."""
    if granted is None:
        user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
        granted = parse_granted_scopes(user.scopes_json if user else "")
    if not has_fittings_access(granted):
        if scope_errors is not None:
            scope_errors["fittings"] = "Missing scope: esi-fittings.read_fittings.v1"
        return 0

    token = await bearer_token(session, character_id=character_id)
    if not token:
        if scope_errors is not None:
            scope_errors["fittings"] = "No valid SSO token — log in again."
        return 0

    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    char_name = user.character_name if user else f"Character {character_id}"
    headers = {"Authorization": f"Bearer {token}", "User-Agent": _UA}

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.get(f"{_ESI}/characters/{character_id}/fittings/", headers=headers)
        if resp.status_code in (401, 403):
            if scope_errors is not None:
                scope_errors["fittings"] = resp.text[:200]
            return 0
        if resp.status_code != 200:
            logger.warning("fittings sync %s HTTP %s", character_id, resp.status_code)
            return 0
        rows = resp.json() or []
    except Exception:
        logger.exception("fittings sync failed for %s", character_id)
        return 0

    type_ids = {int(r.get("ship_type_id") or 0) for r in rows if isinstance(r, dict)}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for item in row.get("items") or []:
            if isinstance(item, dict):
                type_ids.add(int(item.get("type_id") or 0))
    type_names = await load_type_names(session, {tid for tid in type_ids if tid > 0})

    await session.execute(
        delete(FittingRecord).where(FittingRecord.owner_character_id == character_id)
    )

    count = 0
    skipped = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        fitting_id = int(row.get("fitting_id") or 0)
        ship_type_id = int(row.get("ship_type_id") or 0)
        if not fitting_id or not ship_type_id:
            continue
        items = [i for i in (row.get("items") or []) if isinstance(i, dict)]
        ship_name = type_names.get(ship_type_id, f"Type {ship_type_id}")
        module_ids = _module_type_ids(items)
        try:
            session.add(
                FittingRecord(
                    name=str(row.get("name") or "Unnamed fitting")[:256],
                    ship_type_id=ship_type_id,
                    ship_type_name=ship_name[:128],
                    doctrine_slug="",
                    eft_text=_build_eft(ship_name, items, type_names),
                    tags_json=json.dumps({"module_type_ids": module_ids}),
                    public=False,
                    owner_character_id=character_id,
                    owner_character_name=char_name[:128],
                    esi_fitting_id=fitting_id,
                )
            )
            count += 1
        except Exception:
            skipped += 1
            logger.exception("skip fitting %s for character %s", fitting_id, character_id)
    if skipped and scope_errors is not None:
        scope_errors.setdefault(
            "fittings",
            f"Synced {count} fittings; skipped {skipped} oversized/invalid row(s).",
        )
    return count


async def sync_character_blueprints(
    session: AsyncSession,
    character_id: int,
    *,
    granted: set[str] | None = None,
    scope_errors: dict[str, str] | None = None,
) -> int:
    """Pull character blueprint originals/copies from ESI."""
    if granted is None:
        user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
        granted = parse_granted_scopes(user.scopes_json if user else "")
    if not has_blueprints_access(granted):
        if scope_errors is not None:
            scope_errors["blueprints"] = "Missing scope: esi-characters.read_blueprints.v1"
        return 0

    token = await bearer_token(session, character_id=character_id)
    if not token:
        if scope_errors is not None:
            scope_errors["blueprints"] = "No valid SSO token — log in again."
        return 0

    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    char_name = user.character_name if user else f"Character {character_id}"
    headers = {"Authorization": f"Bearer {token}", "User-Agent": _UA}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            page = 1
            rows: list[dict[str, Any]] = []
            while page <= 50:
                resp = await client.get(
                    f"{_ESI}/characters/{character_id}/blueprints/",
                    headers=headers,
                    params={"page": page},
                )
                if resp.status_code in (401, 403):
                    if scope_errors is not None:
                        scope_errors["blueprints"] = resp.text[:200]
                    return 0
                if resp.status_code != 200:
                    break
                chunk = resp.json() or []
                if not chunk:
                    break
                rows.extend(r for r in chunk if isinstance(r, dict))
                if len(chunk) < 1000:
                    break
                page += 1
    except Exception:
        logger.exception("blueprint sync failed for %s", character_id)
        return 0

    type_ids = {int(r.get("type_id") or 0) for r in rows if int(r.get("type_id") or 0) > 0}
    location_ids = {int(r.get("location_id") or 0) for r in rows if int(r.get("location_id") or 0) > 0}
    type_names = await load_type_names(session, type_ids)
    loc_labels = await resolve_location_labels(
        session,
        list(location_ids),
        character_id=character_id,
        access_token=token,
    )

    await session.execute(
        delete(IndyBlueprint).where(IndyBlueprint.owner_character_id == character_id)
    )

    count = 0
    for row in rows:
        item_id = int(row.get("item_id") or 0)
        type_id = int(row.get("type_id") or 0)
        if not item_id or not type_id:
            continue
        loc_id = int(row.get("location_id") or 0)
        loc_name = loc_labels.get(loc_id) or f"Location {loc_id}"
        session.add(
            IndyBlueprint(
                owner_character_name=char_name[:128],
                owner_character_id=character_id,
                item_id=item_id,
                owner_scope="personal",
                type_id=type_id,
                type_name=type_names.get(type_id, f"Type {type_id}")[:256],
                material_efficiency=int(row.get("material_efficiency") or 0),
                time_efficiency=int(row.get("time_efficiency") or 0),
                runs=int(row.get("runs") if row.get("runs") is not None else -1),
                location_name=loc_name[:256],
                shared=False,
                copy_available=int(row.get("runs") or 0) > 0,
            )
        )
        count += 1
    return count


async def sync_character_industry(
    session: AsyncSession,
    character_id: int,
    *,
    granted: set[str] | None = None,
    scope_errors: dict[str, str] | None = None,
) -> dict[str, int]:
    fittings = await sync_character_fittings(
        session, character_id, granted=granted, scope_errors=scope_errors
    )
    blueprints = await sync_character_blueprints(
        session, character_id, granted=granted, scope_errors=scope_errors
    )
    jobs = await sync_character_industry_jobs(
        session, character_id, granted=granted, scope_errors=scope_errors
    )
    mining = await sync_character_mining_ledger(
        session, character_id, granted=granted, scope_errors=scope_errors
    )
    return {"fittings": fittings, "blueprints": blueprints, "jobs": jobs, "mining": mining}


_ACTIVITY_NAMES: dict[int, str] = {
    1: "manufacturing",
    3: "research",
    4: "research",
    5: "copy",
    7: "invention",
    8: "invention",
    11: "reaction",
}


def _parse_esi_dt(value: str | None):
    if not value:
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


async def sync_character_industry_jobs(
    session: AsyncSession,
    character_id: int,
    *,
    granted: set[str] | None = None,
    scope_errors: dict[str, str] | None = None,
) -> int:
    from app.services.audit_scopes import has_industry_jobs_access

    if granted is None:
        user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
        granted = parse_granted_scopes(user.scopes_json if user else "")
    if not has_industry_jobs_access(granted):
        if scope_errors is not None:
            scope_errors["industry_jobs"] = "Missing scope: esi-industry.read_character_jobs.v1"
        return 0

    token = await bearer_token(session, character_id=character_id)
    if not token:
        if scope_errors is not None:
            scope_errors["industry_jobs"] = "No valid SSO token — log in again."
        return 0

    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    char_name = user.character_name if user else f"Character {character_id}"

    try:
        from app.services.esi import esi_get_paged_list

        rows = await esi_get_paged_list(
            f"/characters/{character_id}/industry/jobs/",
            auth=True,
            session=session,
            character_id=character_id,
            max_pages=20,
        )
    except Exception:
        logger.exception("industry jobs sync failed for %s", character_id)
        return 0

    type_ids: set[int] = set()
    facility_ids: set[int] = set()
    installer_ids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        type_ids.add(int(row.get("blueprint_type_id") or 0))
        type_ids.add(int(row.get("product_type_id") or 0))
        fid = int(row.get("facility_id") or 0)
        if fid > 0:
            facility_ids.add(fid)
        iid = int(row.get("installer_id") or 0)
        if iid > 0:
            installer_ids.add(iid)
    type_names = await load_type_names(session, {tid for tid in type_ids if tid > 0})
    installer_names = await resolve_universe_names(list(installer_ids))
    loc_labels = await resolve_location_labels(
        session,
        list(facility_ids),
        character_id=character_id,
    )

    await session.execute(
        delete(IndyJobRecord).where(IndyJobRecord.owner_character_id == character_id)
    )

    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        job_id = int(row.get("job_id") or 0)
        if not job_id:
            continue
        activity_id = int(row.get("activity_id") or 0)
        bp_type = int(row.get("blueprint_type_id") or 0)
        product_type = int(row.get("product_type_id") or 0)
        facility_id = int(row.get("facility_id") or 0)
        installer_id = int(row.get("installer_id") or 0)
        loc_name = loc_labels.get(facility_id) or (
            f"Facility {facility_id}" if facility_id else ""
        )
        session.add(
            IndyJobRecord(
                character_name=char_name[:128],
                owner_character_id=character_id,
                installer_id=installer_id or None,
                installer_name=(installer_names.get(installer_id) or "")[:128],
                job_id=job_id,
                blueprint_name=type_names.get(bp_type, f"Type {bp_type}")[:256],
                activity=_ACTIVITY_NAMES.get(activity_id, f"activity_{activity_id}"),
                runs=int(row.get("runs") or 1),
                status=str(row.get("status") or "active")[:24],
                location_name=loc_name[:256],
                facility_id=facility_id or None,
                started_at=_parse_esi_dt(row.get("start_date")),
                ends_at=_parse_esi_dt(row.get("end_date")),
                output_type_name=type_names.get(product_type, f"Type {product_type}")[:256]
                if product_type
                else "",
            )
        )
        count += 1
    return count


async def sync_character_mining_ledger(
    session: AsyncSession,
    character_id: int,
    *,
    granted: set[str] | None = None,
    scope_errors: dict[str, str] | None = None,
) -> int:
    from datetime import date, timedelta

    from sqlalchemy import and_

    from app.models import MiningLog
    from app.models.tools import SdeSystem
    from app.services.audit_scopes import has_mining_access

    if granted is None:
        user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
        granted = parse_granted_scopes(user.scopes_json if user else "")
    if not has_mining_access(granted):
        if scope_errors is not None:
            scope_errors["mining"] = "Missing scope: esi-industry.read_character_mining.v1"
        return 0

    token = await bearer_token(session, character_id=character_id)
    if not token:
        if scope_errors is not None:
            scope_errors["mining"] = "No valid SSO token — log in again."
        return 0

    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    char_name = user.character_name if user else f"Character {character_id}"
    headers = {"Authorization": f"Bearer {token}", "User-Agent": _UA}
    from_date = (date.today() - timedelta(days=30)).isoformat()

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            page = 1
            rows: list[dict[str, Any]] = []
            while page <= 20:
                resp = await client.get(
                    f"{_ESI}/characters/{character_id}/mining/",
                    headers=headers,
                    params={"page": page},
                )
                if resp.status_code in (401, 403):
                    if scope_errors is not None:
                        scope_errors["mining"] = resp.text[:200]
                    return 0
                if resp.status_code != 200:
                    break
                chunk = resp.json() or []
                if not chunk:
                    break
                for row in chunk:
                    if not isinstance(row, dict):
                        continue
                    row_date = str(row.get("date") or "")[:10]
                    if row_date and row_date >= from_date:
                        rows.append(row)
                if len(chunk) < 1000:
                    break
                page += 1
    except Exception:
        logger.exception("mining ledger sync failed for %s", character_id)
        return 0

    type_ids = {int(r.get("type_id") or 0) for r in rows}
    system_ids = {int(r.get("solar_system_id") or 0) for r in rows}
    type_names = await load_type_names(session, {tid for tid in type_ids if tid > 0})
    sys_names: dict[int, str] = {}
    if system_ids:
        sys_rows = (
            await session.scalars(select(SdeSystem).where(SdeSystem.system_id.in_(system_ids)))
        ).all()
        sys_names = {int(r.system_id): r.name for r in sys_rows}

    await session.execute(
        delete(MiningLog).where(
            and_(MiningLog.character_id == character_id, MiningLog.source == "esi")
        )
    )

    count = 0
    for row in rows:
        type_id = int(row.get("type_id") or 0)
        qty = int(row.get("quantity") or 0)
        system_id = int(row.get("solar_system_id") or 0)
        if not type_id or not qty:
            continue
        mined = date.fromisoformat(str(row.get("date") or "")[:10])
        system_name = sys_names.get(system_id, f"System {system_id}" if system_id else "Unknown")
        session.add(
            MiningLog(
                mined_date=mined,
                structure_name=system_name[:256],
                character_id=character_id,
                character_name=char_name[:128],
                type_name=type_names.get(type_id, f"Type {type_id}")[:128],
                type_id=type_id,
                moon_rarity="esi",
                quantity=qty,
                isk_value=Decimal("0"),
                source="esi",
                system_id=system_id or None,
            )
        )
        count += 1
    return count
