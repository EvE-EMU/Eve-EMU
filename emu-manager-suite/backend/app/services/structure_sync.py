"""Discover player-accessible structures and upsert AuthedStructure rows."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.member_audit import CharacterAsset
from app.models.tools import AuthedStructure, SdeSystem, SsoUser
from app.services.audit_scopes import has_search_structures_access, has_structure_markets_access, parse_granted_scopes
from app.services.audit_snapshot import load_snapshot
from app.services.esi import bearer_token
from app.services.universe_locations import ensure_universe_locations

logger = logging.getLogger(__name__)
_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; structure-sync)"


def is_structure_id(entity_id: int) -> bool:
    return 1_000_000_000_000 <= entity_id < 1_200_000_000_000


async def _collect_structure_ids(
    session: AsyncSession,
    character_id: int,
) -> set[int]:
    from app.models.tools import AuditProfile, CharacterMarketOrder, IndyJobRecord

    ids: set[int] = set()
    profile = await session.scalar(select(AuditProfile).where(AuditProfile.character_id == character_id))
    if profile:
        snap = load_snapshot(profile)
        loc = snap.get("location") if isinstance(snap.get("location"), dict) else {}
        stid = int(loc.get("structure_id") or 0)
        if is_structure_id(stid):
            ids.add(stid)

    assets = (
        await session.scalars(select(CharacterAsset).where(CharacterAsset.character_id == character_id))
    ).all()
    for asset in assets:
        lid = int(asset.location_id or 0)
        if is_structure_id(lid):
            ids.add(lid)

    for row in (
        await session.scalars(
            select(CharacterMarketOrder).where(CharacterMarketOrder.character_id == character_id)
        )
    ).all():
        lid = int(row.location_id or 0)
        if is_structure_id(lid):
            ids.add(lid)

    for row in (
        await session.scalars(
            select(IndyJobRecord).where(IndyJobRecord.owner_character_id == character_id)
        )
    ).all():
        lid = int(row.facility_id or 0)
        if is_structure_id(lid):
            ids.add(lid)

    return ids


async def _search_structures(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    search_term: str,
) -> set[int]:
    term = search_term.strip()
    if len(term) < 3:
        return set()
    resp = await client.get(
        f"{_ESI}/search/",
        params={"categories": "structure", "search": term, "strict": "false"},
        headers=headers,
    )
    if resp.status_code != 200:
        return set()
    body = resp.json()
    if not isinstance(body, dict):
        return set()
    raw = body.get("structure") or []
    return {int(x) for x in raw if int(x or 0) > 0 and is_structure_id(int(x))}


async def _probe_structure_market(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    structure_id: int,
) -> bool:
    resp = await client.get(
        f"{_ESI}/markets/structures/{structure_id}/",
        headers=headers,
        params={"page": 1},
    )
    return resp.status_code == 200


async def sync_character_structures(
    session: AsyncSession,
    character_id: int,
    *,
    granted: set[str] | None = None,
    scope_errors: dict[str, str] | None = None,
) -> int:
    if granted is None:
        user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
        granted = parse_granted_scopes(user.scopes_json if user else "")

    has_structures = has_search_structures_access(granted) or bool(
        {"esi-universe.read_structures.v1", "esi-markets.structure_markets.v1"} & granted
    )
    if not has_structures:
        if scope_errors is not None:
            scope_errors["structures"] = "Missing structure search/read scopes."
        return 0

    token = await bearer_token(session, character_id=character_id)
    if not token:
        if scope_errors is not None:
            scope_errors["structures"] = "No valid SSO token — log in again."
        return 0

    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    structure_ids = await _collect_structure_ids(session, character_id)

    wompstar_id = int(settings.wompstar_structure_id or 0)
    if has_structure_markets_access(granted) and wompstar_id > 0:
        structure_ids.add(wompstar_id)

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": _UA}
    async with httpx.AsyncClient(timeout=45.0) as client:
        if has_search_structures_access(granted) and user:
            for term in _search_terms(user):
                structure_ids.update(await _search_structures(client, headers=headers, search_term=term))

        if not structure_ids:
            return 0

        loc_map = await ensure_universe_locations(
            session,
            list(structure_ids),
            character_id=character_id,
            access_token=token,
        )
        sys_ids = {int(loc.solar_system_id) for loc in loc_map.values() if loc.solar_system_id}
        sys_names: dict[int, str] = {}
        if sys_ids:
            rows = (await session.scalars(select(SdeSystem).where(SdeSystem.system_id.in_(sys_ids)))).all()
            sys_names = {int(r.system_id): r.name for r in rows}

        upserted = 0
        for sid in sorted(structure_ids):
            loc = loc_map.get(sid)
            if not loc:
                continue
            sid_sys = int(loc.solar_system_id or 0)
            sys_label = sys_names.get(sid_sys, "") if sid_sys else ""
            has_market = False
            if has_structure_markets_access(granted):
                try:
                    has_market = await _probe_structure_market(
                        client, headers=headers, structure_id=sid
                    )
                except Exception:
                    logger.debug("structure market probe failed for %s", sid)

            existing = await session.scalar(
                select(AuthedStructure).where(AuthedStructure.structure_id == sid)
            )
            if existing:
                existing.structure_name = loc.name[:256]
                existing.system_name = sys_label[:128] or existing.system_name
                existing.solar_system_id = sid_sys or existing.solar_system_id
                if has_market:
                    existing.has_market = True
                    existing.owner_character_id = character_id
                elif not existing.owner_character_id:
                    existing.owner_character_id = character_id
                existing.updated_at = datetime.now(UTC)
            else:
                session.add(
                    AuthedStructure(
                        structure_id=sid,
                        structure_name=loc.name[:256],
                        system_name=sys_label[:128],
                        solar_system_id=sid_sys,
                        has_market=has_market,
                        has_reprocessing=False,
                        owner_character_id=character_id,
                    )
                )
            upserted += 1
        return upserted


def _search_terms(user: SsoUser) -> list[str]:
    terms: list[str] = []
    for raw in (user.corporation_name, user.alliance_name, user.character_name):
        text = str(raw or "").strip()
        if len(text) >= 3:
            terms.append(text[:64])
    return terms[:3]
