"""EVE SSO session endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.db.session import get_db
from app.models import AuthedStructure, SsoUser
from app.services.auth_session import create_session_token, parse_session_token
from app.services.character_roster import can_switch_to, load_roster
from app.services.eve_sso import (
    build_authorize_url,
    complete_login,
    create_oauth_state,
    parse_oauth_state,
    verify_oauth_state,
)
from app.services.hr_lookup import viewer_has_hr_lookup
from app.services.rbac import UserAuthContext, build_auth_context, normalize_access_level, permissions_for_access_level
from app.services.audit_scopes import missing_scopes, parse_granted_scopes
from app.services.sso_token import probe_character_token

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


class SsoExchangeIn(BaseModel):
    code: str = Field(..., min_length=8)
    state: str = Field(default="")


class SwitchCharacterIn(BaseModel):
    character_id: int = Field(..., gt=0)


def _session_character_id(session_header: str | None) -> int | None:
    return parse_session_token(session_header)


async def _user_payload(db: AsyncSession, user: SsoUser) -> dict:
    roster = await load_roster(db, int(user.character_id))
    ctx = await build_auth_context(db, int(user.character_id))
    access_level = normalize_access_level(ctx.state_name if ctx else None, authenticated=True)
    permissions = sorted(ctx.permissions) if ctx else sorted(permissions_for_access_level(access_level))
    hr_lookup = bool(ctx and await viewer_has_hr_lookup(db, ctx))
    from app.auth.deps import is_administrator

    granted = parse_granted_scopes(user.scopes_json)
    scope_gaps = missing_scopes(granted)

    return {
        "authenticated": True,
        "character_id": user.character_id,
        "character_name": user.character_name,
        "corporation_name": user.corporation_name,
        "alliance_name": user.alliance_name,
        "state": ctx.state_name if ctx else None,
        "state_color": ctx.state_color if ctx else None,
        "access_level": access_level,
        "permissions": permissions,
        "is_administrator": bool(ctx and is_administrator(ctx)),
        "hr_lookup": hr_lookup,
        "token_valid": bool(user.refresh_token_enc),
        "reauthorize_url": "/api/auth/sso/login",
        "missing_scopes": scope_gaps[:16],
        "missing_scope_count": len(scope_gaps),
        "alts": [
            {
                "character_id": r.character_id,
                "character_name": r.character_name,
                "is_main": r.is_main,
                "token_valid": r.token_valid,
            }
            for r in roster
        ],
        "login_url": "/api/auth/sso/login",
        "link_alt_url": "/api/auth/sso/link",
    }


@router.get("/sso/login-url")
async def sso_login_url() -> dict:
    """Return EVE SSO authorize URL when configured; otherwise AA Charlink fallback."""
    if settings.sso_client_id and settings.sso_client_secret:
        state = create_oauth_state(mode="login")
        return {
            "configured": True,
            "url": build_authorize_url(state=state),
            "state": state,
        }
    return {
        "configured": False,
        "url": f"{settings.aa_api_base_url}/account/login/?next=/",
        "message": "Use Alliance Auth login until EMUMS SSO is registered.",
    }


@router.get("/sso/link-url")
async def sso_link_url(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    """Authorize URL to link an additional alt to the current account."""
    if not settings.sso_client_id or not settings.sso_client_secret:
        raise HTTPException(503, detail="EMUMS SSO is not configured.")
    owner = await db.scalar(select(SsoUser).where(SsoUser.character_id == auth.character_id))
    if not owner:
        raise HTTPException(401, detail="Not authenticated")
    state = create_oauth_state(mode="link", owner_user_id=int(owner.id))
    return {
        "url": build_authorize_url(state=state),
        "state": state,
    }


@router.post("/sso/exchange")
async def sso_exchange(body: SsoExchangeIn, db: AsyncSession = Depends(get_db)) -> dict:
    """Exchange SSO authorization code for an EMUMS session token."""
    if not settings.sso_client_id or not settings.sso_client_secret:
        raise HTTPException(503, detail="EMUMS SSO is not configured.")
    if not verify_oauth_state(body.state):
        raise HTTPException(400, detail="Invalid or expired SSO state.")
    state_payload = parse_oauth_state(body.state) or {}
    link_owner_id: int | None = None
    if state_payload.get("mode") == "link":
        owner = state_payload.get("owner")
        if owner is not None:
            link_owner_id = int(owner)
    try:
        result = await complete_login(db, code=body.code.strip(), link_owner_user_id=link_owner_id)
    except RuntimeError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("SSO exchange failed")
        raise HTTPException(503, detail="SSO login temporarily unavailable") from exc
    await db.commit()
    return result


@router.post("/switch")
async def switch_character(
    body: SwitchCharacterIn,
    db: AsyncSession = Depends(get_db),
    x_emums_session: str | None = Header(default=None, alias="X-EMUMS-Session"),
) -> dict:
    """Switch active session to another linked alt."""
    current_id = _session_character_id(x_emums_session)
    if not current_id:
        raise HTTPException(401, detail="Not authenticated")
    if not await can_switch_to(db, current_character_id=current_id, target_character_id=body.character_id):
        raise HTTPException(403, detail="Character is not on your linked roster")
    user = await db.scalar(select(SsoUser).where(SsoUser.character_id == body.character_id))
    if not user or not user.refresh_token_enc:
        raise HTTPException(400, detail="Alt has no valid ESI token — link again via SSO")
    if not await probe_character_token(db, int(body.character_id)):
        raise HTTPException(
            400,
            detail="Alt ESI token expired — re-link via SSO from your main character",
        )
    await db.commit()
    token = create_session_token(int(body.character_id))
    return {
        "session_token": token,
        "character_id": int(body.character_id),
        "character_name": user.character_name,
    }


@router.get("/me")
async def auth_me(
    db: AsyncSession = Depends(get_db),
    x_emums_session: str | None = Header(default=None, alias="X-EMUMS-Session"),
) -> dict:
    """Current session — uses signed session cookie forwarded by the Next.js BFF."""
    character_id = _session_character_id(x_emums_session)
    if character_id:
        user = await db.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
        if user:
            token_ok = await probe_character_token(db, int(user.character_id))
            payload = await _user_payload(db, user)
            payload["token_valid"] = token_ok
            if not token_ok:
                payload["auth_notice"] = "reauthorize"
            elif payload.get("missing_scope_count"):
                payload["auth_notice"] = "missing_scopes"
            await db.commit()
            return payload

    return {
        "authenticated": False,
        "character_id": None,
        "character_name": None,
        "state": None,
        "access_level": "public",
        "permissions": sorted(permissions_for_access_level("public")),
        "hr_lookup": False,
        "token_valid": False,
        "alts": [],
        "login_url": "/api/auth/sso/login",
        "reauthorize_url": "/api/auth/sso/login",
    }


@router.get("/structures")
async def my_structures(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Structures available via authed characters (market/reprocessing)."""
    rows = (await db.scalars(select(AuthedStructure).order_by(AuthedStructure.structure_name))).all()
    return [
        {
            "structure_id": r.structure_id,
            "structure_name": r.structure_name,
            "system_name": r.system_name,
            "has_market": r.has_market,
            "has_reprocessing": r.has_reprocessing,
        }
        for r in rows
    ]
