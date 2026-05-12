"""EVE Online SSO (OAuth2) — authorize redirect and callback (Discord link flow)."""

from __future__ import annotations

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.auth.sso_link_service import handle_eve_oauth_callback
from app.config import settings
from app.db.models import DiscordPendingSsoLink
from app.db.session import session_scope

router = APIRouter(prefix="/auth/eve", tags=["Auth"])


@router.get("/start")
async def eve_sso_start(
    return_to: str | None = Query(None, description="Optional opaque state (non-Discord flows)"),
    link_id: UUID | None = Query(None, description="Discord /settings link session id from core"),
):
    """Redirect browser to CCP SSO authorize endpoint."""
    if not settings.sso_client_id:
        raise HTTPException(
            status_code=503,
            detail="SSO not configured: set CORE_SSO_CLIENT_ID and CORE_SSO_CLIENT_SECRET.",
        )

    ccp_state = ""
    if link_id is not None:
        if not settings.database_url:
            raise HTTPException(status_code=503, detail="CORE_DATABASE_URL is not set.")
        async with session_scope() as session:
            row = await session.get(DiscordPendingSsoLink, link_id)
        if row is None:
            raise HTTPException(
                status_code=400,
                detail="Unknown link_id. Run /settings link in Discord again.",
            )
        ccp_state = str(link_id)
    else:
        ccp_state = return_to or ""

    params = {
        "response_type": "code",
        "redirect_uri": settings.sso_callback_url,
        "client_id": settings.sso_client_id,
        "scope": settings.sso_scopes,
        "state": ccp_state,
    }
    url = f"{settings.sso_authorize_url}?{urlencode(params)}"
    return RedirectResponse(url, status_code=302)


@router.get("/callback")
async def eve_sso_callback(code: str | None = None, state: str | None = None):
    """Exchange authorization code, link Discord when ``state`` is a pending ``link_id``."""
    return await handle_eve_oauth_callback(code=code, state=state)
