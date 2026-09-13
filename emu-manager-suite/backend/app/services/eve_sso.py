"""EVE Online SSO — authorize URL, code exchange, EMUMS user upsert."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import LinkedCharacter, SsoUser
from app.services.auth_session import create_session_token
from app.services.eve_jwt import character_id_from_payload, character_name_from_payload, decode_jwt_payload
from app.services.esi import esi_get

logger = logging.getLogger(__name__)

_TOKEN = "https://login.eveonline.com/v2/oauth/token"
_AUTHORIZE = "https://login.eveonline.com/v2/oauth/authorize"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; sso)"


def _basic_auth() -> str:
    raw = f"{settings.sso_client_id}:{settings.sso_client_secret}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _state_secret() -> bytes:
    return (settings.session_secret or settings.api_key or "emums-dev").encode()


def create_oauth_state(*, mode: str = "login", owner_user_id: int | None = None) -> str:
    payload: dict[str, int | str] = {
        "n": secrets.token_urlsafe(8),
        "exp": int(time.time()) + 900,
        "mode": mode,
    }
    if owner_user_id is not None:
        payload["owner"] = int(owner_user_id)
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_state_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def parse_oauth_state(state: str | None) -> dict[str, Any] | None:
    if not state or "." not in state:
        return None
    body, sig = state.rsplit(".", 1)
    expected = hmac.new(_state_secret(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    pad = "=" * (-len(body) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode((body + pad).encode()))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp") or 0) < int(time.time()):
        return None
    return payload if isinstance(payload, dict) else None


def verify_oauth_state(state: str | None) -> bool:
    return parse_oauth_state(state) is not None


def build_authorize_url(*, state: str) -> str:
    params = {
        "response_type": "code",
        "redirect_uri": settings.sso_callback_url,
        "client_id": settings.sso_client_id,
        "scope": settings.sso_scopes,
        "state": state,
    }
    return f"{_AUTHORIZE}?{urlencode(params)}"


async def exchange_authorization_code(code: str) -> dict[str, Any]:
    headers = {
        "Authorization": _basic_auth(),
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": _UA,
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.sso_callback_url,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(_TOKEN, headers=headers, data=data)
    if resp.status_code != 200:
        raise RuntimeError(f"SSO token exchange failed: HTTP {resp.status_code}")
    body = resp.json()
    return body if isinstance(body, dict) else {}


async def _character_corp_info(character_id: int) -> tuple[int, str, int | None, str]:
    status, data = await esi_get(f"/characters/{character_id}/", auth=False)
    if status != 200 or not isinstance(data, dict):
        return 0, "", None, ""
    corp_id = int(data.get("corporation_id") or 0)
    alliance_id = data.get("alliance_id")
    corp_name = ""
    alliance_name = ""
    if corp_id:
        cs, corp = await esi_get(f"/corporations/{corp_id}/", auth=False)
        if cs == 200 and isinstance(corp, dict):
            corp_name = str(corp.get("name") or "")
    if alliance_id:
        aid = int(alliance_id)
        as_, ali = await esi_get(f"/alliances/{aid}/", auth=False)
        if as_ == 200 and isinstance(ali, dict):
            alliance_name = str(ali.get("name") or "")
        return corp_id, corp_name, aid, alliance_name
    return corp_id, corp_name, None, alliance_name


async def complete_login(
    session: AsyncSession,
    *,
    code: str,
    link_owner_user_id: int | None = None,
) -> dict[str, Any]:
    token_payload = await exchange_authorization_code(code)
    access = str(token_payload.get("access_token") or "")
    refresh = str(token_payload.get("refresh_token") or "")
    if not access or not refresh:
        raise RuntimeError("SSO response missing tokens")

    jwt = decode_jwt_payload(access)
    character_id = character_id_from_payload(jwt)
    character_name = character_name_from_payload(jwt) or f"Character {character_id}"
    if not character_id:
        raise RuntimeError("Could not resolve character id from SSO token")

    corp_id, corp_name, alliance_id, alliance_name = await _character_corp_info(character_id)
    scopes = str(token_payload.get("scope") or settings.sso_scopes)
    now = datetime.now(UTC)

    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    if user is None:
        user = SsoUser(
            character_id=character_id,
            character_name=character_name,
        )
        session.add(user)
    user.character_name = character_name
    user.corporation_id = corp_id
    user.corporation_name = corp_name
    user.alliance_id = alliance_id
    user.alliance_name = alliance_name
    user.access_token_enc = access
    user.refresh_token_enc = refresh
    user.scopes_json = json.dumps([s for s in scopes.split() if s.strip()])
    user.last_login_at = now
    await session.flush()

    from app.services.sso_token import invalidate_roster_cache_for_character, set_character_token_valid

    await set_character_token_valid(session, character_id, valid=True)

    try:
        from app.tasks.member_audit import sync_character_audit_task

        sync_character_audit_task.apply_async(args=[character_id], queue="audit")
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Post-login audit sync failed for %s", character_id)

    if link_owner_user_id is not None:
        owner = await session.get(SsoUser, int(link_owner_user_id))
        if owner is None:
            raise RuntimeError("Invalid link owner account")
        if int(owner.character_id) == int(character_id):
            raise RuntimeError("Cannot link your active character as an alt")
        linked = await session.scalar(
            select(LinkedCharacter).where(
                LinkedCharacter.owner_user_id == owner.id,
                LinkedCharacter.character_id == character_id,
            )
        )
        if linked is None:
            session.add(
                LinkedCharacter(
                    owner_user_id=owner.id,
                    character_id=character_id,
                    character_name=character_name,
                    corporation_id=corp_id,
                    is_main=False,
                    token_valid=True,
                    scopes_json=user.scopes_json,
                )
            )
        else:
            linked.character_name = character_name
            linked.corporation_id = corp_id
            linked.token_valid = True
            linked.scopes_json = user.scopes_json
        await invalidate_roster_cache_for_character(session, int(owner.character_id))
        try:
            from app.tasks.member_audit import sync_character_audit_task

            sync_character_audit_task.apply_async(args=[character_id], queue="audit")
        except Exception:
            logger.exception("Post-link audit sync failed for %s", character_id)
        return {
            "linked": True,
            "character_id": character_id,
            "character_name": character_name,
        }

    linked = await session.scalar(
        select(LinkedCharacter).where(
            LinkedCharacter.owner_user_id == user.id,
            LinkedCharacter.character_id == character_id,
        )
    )
    if linked is None:
        session.add(
            LinkedCharacter(
                owner_user_id=user.id,
                character_id=character_id,
                character_name=character_name,
                corporation_id=corp_id,
                is_main=True,
                token_valid=True,
                scopes_json=user.scopes_json,
            )
        )

    await invalidate_roster_cache_for_character(session, character_id)
    session_token = create_session_token(character_id)
    return {
        "session_token": session_token,
        "character_id": character_id,
        "character_name": character_name,
        "corporation_name": corp_name,
        "alliance_name": alliance_name,
    }
