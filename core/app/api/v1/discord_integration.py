"""Discord bot integration: link intent + rank sync (Bearer ``CORE_DISCORD_BOT_SECRET``)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.bot_secret import require_discord_bot_secret
from app.config import settings
from app.db.models import DiscordPendingSsoLink
from app.db.session import session_scope
from app.services.fg_rank import compute_fg_rank_for_discord

router = APIRouter(prefix="/integrations/discord", tags=["Discord integration"])


class PrepareLinkIn(BaseModel):
    discord_user_id: int = Field(..., ge=1)


class PrepareLinkOut(BaseModel):
    link_url: str


class SyncRolesIn(BaseModel):
    discord_user_id: int = Field(..., ge=1)


class SyncRolesOut(BaseModel):
    linked: bool
    rank_key: str
    detail: str = ""


@router.post("/prepare-link", response_model=PrepareLinkOut)
async def prepare_discord_link(
    body: PrepareLinkIn,
    authorization: Annotated[str | None, Header()] = None,
) -> PrepareLinkOut:
    """Create a short-lived SSO session; open ``link_url`` in a browser to complete EVE login."""
    require_discord_bot_secret(authorization)
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="CORE_DATABASE_URL is not set.")
    if not (settings.sso_client_id and settings.sso_client_secret):
        raise HTTPException(status_code=503, detail="SSO client is not configured on core.")

    link_id = uuid.uuid4()
    async with session_scope() as session:
        session.add(DiscordPendingSsoLink(link_id=link_id, discord_user_id=body.discord_user_id))
        await session.commit()

    base = (settings.public_base_url or "").rstrip("/")
    url = f"{base}/v1/auth/eve/start?link_id={link_id}"
    return PrepareLinkOut(link_url=url)


@router.post("/sync-roles", response_model=SyncRolesOut)
async def sync_roles_payload(
    body: SyncRolesIn,
    authorization: Annotated[str | None, Header()] = None,
) -> SyncRolesOut:
    """Return rank slug for the Discord user; the bot maps slugs to guild roles."""
    require_discord_bot_secret(authorization)
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="CORE_DATABASE_URL is not set.")

    r = await compute_fg_rank_for_discord(body.discord_user_id)
    return SyncRolesOut(linked=r.linked, rank_key=r.rank_key, detail=r.detail)
