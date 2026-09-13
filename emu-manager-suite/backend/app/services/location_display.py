"""Human-readable labels for EVE location / structure entity IDs."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member_audit import CharacterAsset
from app.models.tools import AuthedStructure, IndustrialBuildStructure, SsoUser
from app.services.audit_scopes import parse_granted_scopes
from app.services.character_roster import roster_character_ids
from app.services.esi import bearer_token
from app.services.universe_locations import ensure_universe_locations

logger = logging.getLogger(__name__)
_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; location-display)"
_STRUCTURE_READ_SCOPE = "esi-universe.read_structures.v1"


def _is_station(entity_id: int) -> bool:
    return 60_000_000 <= entity_id < 64_000_000


def _is_structure(entity_id: int) -> bool:
    return 1_000_000_000_000 <= entity_id < 1_200_000_000_000


def looks_unresolved_location_name(name: str, entity_id: int) -> bool:
    text = (name or "").strip()
    if not text:
        return True
    if text == str(entity_id):
        return True
    for prefix in ("Location ", "Structure ", "Facility ", "Station "):
        if text.startswith(prefix):
            suffix = text[len(prefix) :].strip()
            if suffix.isdigit() and int(suffix) == entity_id:
                return True
    return False


async def _known_structure_names(session: AsyncSession, entity_ids: list[int]) -> dict[int, str]:
    if not entity_ids:
        return {}
    out: dict[int, str] = {}
    authed = (
        await session.scalars(
            select(AuthedStructure).where(AuthedStructure.structure_id.in_(entity_ids))
        )
    ).all()
    for row in authed:
        if row.structure_name:
            out[int(row.structure_id)] = row.structure_name
    build = (
        await session.scalars(
            select(IndustrialBuildStructure).where(
                IndustrialBuildStructure.structure_id.in_(entity_ids)
            )
        )
    ).all()
    for row in build:
        if row.structure_name and int(row.structure_id) not in out:
            out[int(row.structure_id)] = row.structure_name
    return out


async def _structure_tokens(session: AsyncSession, preferred_character_id: int | None) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()

    async def add_token(character_id: int | None) -> None:
        if not character_id:
            return
        token = await bearer_token(session, character_id=character_id)
        if token and token not in seen:
            seen.add(token)
            tokens.append(token)

    await add_token(preferred_character_id)
    if preferred_character_id:
        roster_ids = await roster_character_ids(session, int(preferred_character_id))
    else:
        roster_ids = set()
    for cid in sorted(roster_ids):
        user = await session.scalar(select(SsoUser).where(SsoUser.character_id == cid))
        if not user or not user.refresh_token_enc:
            continue
        granted = parse_granted_scopes(user.scopes_json)
        if _STRUCTURE_READ_SCOPE in granted:
            await add_token(int(cid))
    return tokens


async def _resolve_structure_name(
    client: httpx.AsyncClient,
    structure_id: int,
    tokens: list[str],
) -> str | None:
    headers = {"Accept": "application/json", "User-Agent": _UA}
    for token in tokens:
        headers["Authorization"] = f"Bearer {token}"
        resp = await client.get(f"{_ESI}/universe/structures/{structure_id}/", headers=headers)
        if resp.status_code == 200:
            body = resp.json()
            if isinstance(body, dict):
                name = str(body.get("name") or "").strip()
                if name:
                    return name
    return None


async def _load_asset_index(
    session: AsyncSession, character_id: int
) -> dict[int, CharacterAsset]:
    rows = (
        await session.scalars(
            select(CharacterAsset).where(CharacterAsset.character_id == character_id)
        )
    ).all()
    return {int(row.item_id): row for row in rows}


async def _label_from_asset_chain(
    session: AsyncSession,
    start_id: int,
    asset_by_item: dict[int, CharacterAsset],
    root_labels: dict[int, str],
    *,
    character_id: int | None,
    access_token: str | None,
) -> str | None:
    """Walk nested hangar containers up to a station/structure name."""
    chain: list[str] = []
    current = start_id
    seen: set[int] = set()
    while current > 0 and current not in seen:
        seen.add(current)
        asset = asset_by_item.get(current)
        if asset is not None:
            label = (asset.custom_name or "").strip() or (asset.type_name or "").strip()
            if label:
                chain.insert(0, label)
            current = int(asset.location_id or 0)
            continue
        if _is_station(current) or _is_structure(current):
            root = root_labels.get(current, "")
            if root and not looks_unresolved_location_name(root, current):
                chain.insert(0, root)
            else:
                extra = await resolve_location_labels(
                    session,
                    [current],
                    character_id=character_id,
                    access_token=access_token,
                    allow_asset_chain=False,
                )
                resolved = extra.get(current, "")
                if resolved and not looks_unresolved_location_name(resolved, current):
                    chain.insert(0, resolved)
            break
        break
    if not chain:
        return None
    return " › ".join(chain)


async def resolve_location_labels(
    session: AsyncSession,
    entity_ids: list[int],
    *,
    character_id: int | None = None,
    access_token: str | None = None,
    allow_asset_chain: bool = True,
) -> dict[int, str]:
    """Map location entity IDs to display names (stations, structures, systems)."""
    unique = sorted({int(i) for i in entity_ids if int(i) > 0})
    if not unique:
        return {}

    token = access_token or (
        await bearer_token(session, character_id=character_id) if character_id else None
    )
    loc_map = await ensure_universe_locations(
        session,
        unique,
        character_id=character_id,
        access_token=token,
    )
    known = await _known_structure_names(session, [e for e in unique if e >= 1_000_000_000_000])

    unresolved_structures: list[int] = []
    labels: dict[int, str] = {}
    for eid in unique:
        row = loc_map.get(eid)
        name = (row.name if row else "") or known.get(eid, "")
        if name and not looks_unresolved_location_name(name, eid):
            labels[eid] = name
        elif eid >= 1_000_000_000_000:
            unresolved_structures.append(eid)
        elif known.get(eid):
            labels[eid] = known[eid]
        else:
            labels[eid] = name or f"Location {eid}"

    if unresolved_structures:
        tokens = [token] if token else []
        extra = await _structure_tokens(session, character_id)
        for t in extra:
            if t not in tokens:
                tokens.append(t)
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                for sid in unresolved_structures:
                    if sid in labels:
                        continue
                    resolved = known.get(sid) or await _resolve_structure_name(
                        client, sid, tokens
                    )
                    if resolved:
                        labels[sid] = resolved
                        row = loc_map.get(sid)
                        if row:
                            row.name = resolved
                        continue
                    labels[sid] = known.get(sid) or f"Structure {sid}"
        except Exception:
            logger.exception("structure label resolve failed")
            for sid in unresolved_structures:
                labels.setdefault(sid, known.get(sid) or f"Structure {sid}")

    if character_id and allow_asset_chain:
        asset_by_item = await _load_asset_index(session, character_id)
        if asset_by_item:
            for eid in unique:
                current = labels.get(eid, "")
                if current and not looks_unresolved_location_name(current, eid):
                    continue
                chained = await _label_from_asset_chain(
                    session,
                    eid,
                    asset_by_item,
                    labels,
                    character_id=character_id,
                    access_token=token,
                )
                if chained:
                    labels[eid] = chained

    return labels
