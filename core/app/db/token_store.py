"""Persist EVE OAuth tokens in Postgres (survives container restarts when DB uses a named volume)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EveOAuthToken
from app.db.session import session_scope
from app.services.token_cipher import TokenCipher


async def upsert_eve_refresh_token(
    *,
    character_id: int,
    refresh_token: str,
    scopes: str,
    owner_user_id: uuid.UUID | None = None,
    access_token: str | None = None,
    access_expires_at: datetime | None = None,
) -> None:
    """Encrypt and store (or update) refresh token for a character; optionally store access token."""
    cipher = TokenCipher.require()
    blob = cipher.encrypt(refresh_token.encode("utf-8"))
    access_blob: bytes | None = None
    if access_token:
        access_blob = cipher.encrypt(access_token.encode("utf-8"))
    now = datetime.now(UTC)
    async with session_scope() as session:
        await upsert_eve_refresh_token_in_session(
            session,
            character_id=character_id,
            refresh_token=refresh_token,
            scopes=scopes,
            owner_user_id=owner_user_id,
            access_token=access_token,
            access_expires_at=access_expires_at,
        )
        await session.commit()


async def upsert_eve_refresh_token_in_session(
    session: AsyncSession,
    *,
    character_id: int,
    refresh_token: str,
    scopes: str,
    owner_user_id: uuid.UUID | None = None,
    access_token: str | None = None,
    access_expires_at: datetime | None = None,
) -> None:
    """Same as ``upsert_eve_refresh_token`` but uses an existing session (single transaction)."""
    cipher = TokenCipher.require()
    blob = cipher.encrypt(refresh_token.encode("utf-8"))
    access_blob: bytes | None = None
    if access_token:
        access_blob = cipher.encrypt(access_token.encode("utf-8"))
    now = datetime.now(UTC)
    row = await session.scalar(select(EveOAuthToken).where(EveOAuthToken.character_id == character_id))
    if row:
        row.refresh_token_enc = blob
        row.scopes = scopes
        row.updated_at = now
        if owner_user_id is not None:
            row.owner_user_id = owner_user_id
        if access_blob is not None:
            row.access_token_enc = access_blob
        if access_expires_at is not None:
            row.access_expires_at = access_expires_at
    else:
        session.add(
            EveOAuthToken(
                character_id=character_id,
                owner_user_id=owner_user_id,
                refresh_token_enc=blob,
                access_token_enc=access_blob,
                access_expires_at=access_expires_at,
                scopes=scopes,
            )
        )


async def get_eve_refresh_token_plain(*, character_id: int) -> str | None:
    """Decrypt refresh token for server-side ESI calls, or ``None`` if missing."""
    async with session_scope() as session:
        row = await session.scalar(select(EveOAuthToken).where(EveOAuthToken.character_id == character_id))
        if row is None:
            return None
        blob = row.refresh_token_enc
    cipher = TokenCipher.require()
    return cipher.decrypt(blob).decode("utf-8")
