"""ESI token health — refresh persistence, invalidation, roster cache."""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tools import LinkedCharacter, SsoUser
from app.services.cache_ttl import cache_delete_prefix, cache_get, cache_set
from app.services.character_roster import resolve_owner_user_id

logger = logging.getLogger(__name__)

_TOKEN_OK_TTL = 300


async def invalidate_roster_cache_for_character(session: AsyncSession, character_id: int) -> None:
    from app.services.character_roster import unified_roster_character_ids

    char_ids = await unified_roster_character_ids(session, character_id)
    for cid in char_ids:
        await cache_delete_prefix(f"roster:unified:{cid}")
        await cache_delete_prefix(f"roster:solo:{cid}")
    owner_id = await resolve_owner_user_id(session, character_id)
    if owner_id is not None:
        await cache_delete_prefix(f"roster:owner:{owner_id}")


async def set_character_token_valid(
    session: AsyncSession,
    character_id: int,
    *,
    valid: bool,
) -> None:
    cid = int(character_id)
    rows = (await session.scalars(select(LinkedCharacter).where(LinkedCharacter.character_id == cid))).all()
    for row in rows:
        row.token_valid = valid
    await invalidate_roster_cache_for_character(session, cid)
    await cache_set(f"token_ok:{cid}", valid, ttl_seconds=_TOKEN_OK_TTL)


async def persist_token_response(
    session: AsyncSession,
    user: SsoUser,
    body: dict,
) -> None:
    """Save rotated tokens and scopes from CCP token endpoint."""
    access = str(body.get("access_token") or "")
    refresh = str(body.get("refresh_token") or "")
    if access:
        user.access_token_enc = access
    if refresh:
        user.refresh_token_enc = refresh
    scope = body.get("scope")
    if scope:
        scopes = scope if isinstance(scope, str) else " ".join(scope)
        user.scopes_json = json.dumps([s for s in str(scopes).split() if s.strip()])
    await set_character_token_valid(session, int(user.character_id), valid=True)


async def probe_character_token(session: AsyncSession, character_id: int) -> bool:
    """Return whether refresh token still works; uses short TTL cache."""
    cid = int(character_id)
    cached = await cache_get(f"token_ok:{cid}")
    if cached is not None:
        return bool(cached)

    from app.services.esi import refresh_user_access_token

    token = await refresh_user_access_token(session, cid, force=True)
    return token is not None
