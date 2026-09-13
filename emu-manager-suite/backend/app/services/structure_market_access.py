"""Resolve coalition characters that can read structure markets via ESI."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.tools import AuthedStructure, SsoUser
from app.services.audit_scopes import has_structure_markets_access, parse_granted_scopes
from app.services.esi import bearer_token, esi_get

logger = logging.getLogger(__name__)


def bootstrap_character_ids() -> list[int]:
    raw = os.environ.get("EMUMS_BOOTSTRAP_ADMIN_CHARACTER_IDS", "715529239")
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]


async def characters_with_structure_market_scope(session: AsyncSession) -> list[int]:
    """All SSO characters with structure market scope and a refresh token."""
    out: list[int] = []
    for user in (await session.scalars(select(SsoUser))).all():
        if not user.refresh_token_enc:
            continue
        if has_structure_markets_access(parse_granted_scopes(user.scopes_json)):
            out.append(int(user.character_id))
    return out


async def structure_market_candidates(
    session: AsyncSession,
    structure_id: int,
) -> list[int]:
    """Character IDs to try, highest priority first."""
    scoped = set(await characters_with_structure_market_scope(session))
    if not scoped:
        return []

    seen: set[int] = set()
    ordered: list[int] = []

    def add(cid: int) -> None:
        if cid <= 0 or cid in seen or cid not in scoped:
            return
        seen.add(cid)
        ordered.append(cid)

    row = await session.scalar(
        select(AuthedStructure).where(AuthedStructure.structure_id == structure_id)
    )
    if row and row.owner_character_id:
        add(int(row.owner_character_id))

    for cid in bootstrap_character_ids():
        add(cid)

    for cid in sorted(scoped):
        add(cid)

    return ordered


async def probe_structure_market_access(
    session: AsyncSession,
    *,
    structure_id: int,
    character_id: int,
) -> bool:
    token = await bearer_token(session, character_id=character_id)
    if not token:
        return False
    status, _ = await esi_get(
        f"/markets/structures/{structure_id}/",
        params={"page": 1},
        auth=True,
        session=session,
        character_id=character_id,
    )
    return status == 200


async def _set_structure_owner(
    session: AsyncSession,
    *,
    structure_id: int,
    character_id: int,
) -> None:
    row = await session.scalar(
        select(AuthedStructure).where(AuthedStructure.structure_id == structure_id)
    )
    if row:
        row.owner_character_id = character_id
        row.has_market = True
        row.updated_at = datetime.now(UTC)
        return

    session.add(
        AuthedStructure(
            structure_id=structure_id,
            structure_name=f"Structure {structure_id}",
            system_name="",
            has_market=True,
            has_reprocessing=False,
            owner_character_id=character_id,
            solar_system_id=0,
        )
    )


async def resolve_structure_market_character(
    session: AsyncSession,
    structure_id: int,
    *,
    update_owner: bool = True,
) -> int | None:
    """Return a character_id whose token can read this structure's market."""
    for cid in await structure_market_candidates(session, structure_id):
        try:
            if await probe_structure_market_access(
                session, structure_id=structure_id, character_id=cid
            ):
                if update_owner:
                    await _set_structure_owner(
                        session, structure_id=structure_id, character_id=cid
                    )
                return cid
        except Exception:
            logger.debug(
                "structure market probe failed structure=%s character=%s",
                structure_id,
                cid,
                exc_info=True,
            )
    return None


async def refresh_authed_structure_market_owners(session: AsyncSession) -> int:
    """Re-resolve token owners for coalition structures with markets."""
    rows = (
        await session.scalars(
            select(AuthedStructure).where(AuthedStructure.has_market.is_(True))
        )
    ).all()
    updated = 0
    seen: set[int] = set()
    for row in rows:
        seen.add(int(row.structure_id))
        cid = await resolve_structure_market_character(
            session, int(row.structure_id), update_owner=True
        )
        if cid:
            updated += 1
        else:
            logger.warning(
                "No coalition token can read structure market %s (%s)",
                row.structure_id,
                row.structure_name,
            )

    wompstar_id = int(settings.wompstar_structure_id or 0)
    if wompstar_id > 0 and wompstar_id not in seen:
        cid = await resolve_structure_market_character(
            session, wompstar_id, update_owner=True
        )
        if cid:
            updated += 1
    return updated
