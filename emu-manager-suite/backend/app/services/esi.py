"""Minimal ESI HTTP client for EMUMS market browser."""

from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import SsoUser

logger = logging.getLogger(__name__)

_ESI = "https://esi.evetech.net/latest"
_TOKEN = "https://login.eveonline.com/v2/oauth/token"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; market-browser)"

_access_token: str | None = None
_access_expires: datetime | None = None


def _basic_auth_header() -> str:
    return base64.b64encode(
        f"{settings.sso_client_id}:{settings.sso_client_secret}".encode()
    ).decode()


def _token_configured() -> bool:
    rt = (settings.esi_refresh_token or "").strip()
    return bool(settings.sso_client_id and settings.sso_client_secret and rt and not rt.startswith("#"))


async def _refresh_from_env() -> str | None:
    global _access_token, _access_expires
    if not _token_configured():
        return None
    headers = {
        "Authorization": f"Basic {_basic_auth_header()}",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": _UA,
    }
    data = {"grant_type": "refresh_token", "refresh_token": settings.esi_refresh_token.strip()}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(_TOKEN, headers=headers, data=data)
    if resp.status_code != 200:
        logger.warning("ESI token refresh failed: %s", resp.status_code)
        return None
    body = resp.json()
    token = str(body.get("access_token") or "")
    if not token:
        return None
    _access_token = token
    try:
        _access_expires = datetime.now(UTC) + timedelta(seconds=int(body.get("expires_in") or 1200) - 60)
    except (TypeError, ValueError):
        _access_expires = datetime.now(UTC) + timedelta(minutes=15)
    return token


async def refresh_user_access_token(
    session: AsyncSession,
    character_id: int,
    *,
    force: bool = False,
) -> str | None:
    """Refresh a pilot's ESI access token; persist rotation and mark validity."""
    from app.services.sso_token import persist_token_response, set_character_token_valid

    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    if not user or not user.refresh_token_enc or not settings.sso_client_id:
        if user:
            await set_character_token_valid(session, character_id, valid=False)
        return None

    headers = {
        "Authorization": f"Basic {_basic_auth_header()}",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": _UA,
    }
    data = {"grant_type": "refresh_token", "refresh_token": user.refresh_token_enc}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(_TOKEN, headers=headers, data=data)

    if resp.status_code != 200:
        logger.warning(
            "ESI refresh failed for character %s: HTTP %s",
            character_id,
            resp.status_code,
        )
        await set_character_token_valid(session, character_id, valid=False)
        user.access_token_enc = ""
        await session.flush()
        return None

    body = resp.json()
    if not isinstance(body, dict):
        await set_character_token_valid(session, character_id, valid=False)
        return None

    access = str(body.get("access_token") or "")
    if not access:
        await set_character_token_valid(session, character_id, valid=False)
        return None

    await persist_token_response(session, user, body)
    await session.flush()
    return access


async def _refresh_from_user(session: AsyncSession, character_id: int) -> str | None:
    return await refresh_user_access_token(session, character_id, force=True)


async def bearer_token(session: AsyncSession | None = None, *, character_id: int | None = None) -> str | None:
    global _access_token, _access_expires
    if character_id and session:
        token = await _refresh_from_user(session, character_id)
        if token:
            return token
    if _access_token and _access_expires and datetime.now(UTC) < _access_expires:
        return _access_token
    return await _refresh_from_env()


async def esi_get(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    auth: bool = False,
    session: AsyncSession | None = None,
    character_id: int | None = None,
) -> tuple[int, Any]:
    url = path if path.startswith("http") else f"{_ESI}{path}"
    headers = {"Accept": "application/json", "User-Agent": _UA}
    if auth:
        token = await bearer_token(session, character_id=character_id)
        if not token:
            return 401, {"error": "esi_not_authenticated"}
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.get(url, params=params, headers=headers)

    if resp.status_code != 200:
        try:
            body = resp.json()
        except Exception:
            body = {"error": resp.text[:200]}
        return resp.status_code, body

    return 200, resp.json()


async def esi_get_paged_list(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    auth: bool = False,
    session: AsyncSession | None = None,
    character_id: int | None = None,
    max_pages: int = 20,
) -> list[Any]:
    out: list[Any] = []
    page = 1
    base_params = dict(params or {})
    while page <= max_pages:
        status, body = await esi_get(
            path,
            params={**base_params, "page": page},
            auth=auth,
            session=session,
            character_id=character_id,
        )
        if status != 200 or not isinstance(body, list):
            break
        if not body:
            break
        out.extend(body)
        if len(body) < 1000:
            break
        page += 1
    return out


async def resolve_universe_names(ids: list[int]) -> dict[int, str]:
    """Public ESI name lookup for stations, structures, systems."""
    unique = sorted({int(i) for i in ids if int(i) > 0})
    if not unique:
        return {}
    names: dict[int, str] = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for offset in range(0, len(unique), 1000):
            chunk = unique[offset : offset + 1000]
            resp = await client.post(
                f"{_ESI}/universe/names/",
                json=chunk,
                headers={"Accept": "application/json", "User-Agent": _UA},
            )
            if resp.status_code != 200:
                continue
            for row in resp.json() or []:
                if not isinstance(row, dict):
                    continue
                rid = int(row.get("id") or 0)
                if rid > 0:
                    names[rid] = str(row.get("name") or f"ID {rid}")
    return names
