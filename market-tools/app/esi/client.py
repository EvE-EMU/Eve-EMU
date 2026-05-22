"""ESI HTTP client for market-tools (dedicated app credentials + refresh token)."""

from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import settings
from app.esi.aa_bridge import aa_bridge_access_token
from app.esi.rate_limit import acquire_slot, note_error_limit

_ESI = "https://esi.evetech.net/latest"
_TOKEN = "https://login.eveonline.com/v2/oauth/token"
_UA = "EVE-EMU-Market/1.0 (+https://eve-emu.com; market-tools)"

logger = logging.getLogger(__name__)

_access_token: str | None = None
_access_expires: datetime | None = None


async def _refresh_access() -> str | None:
    global _access_token, _access_expires
    if not settings.esi_client_id or not settings.esi_refresh_token:
        return None
    basic = base64.b64encode(
        f"{settings.esi_client_id}:{settings.esi_client_secret}".encode()
    ).decode()
    headers = {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": _UA,
    }
    data = {"grant_type": "refresh_token", "refresh_token": settings.esi_refresh_token}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(_TOKEN, headers=headers, data=data)
    if resp.status_code != 200:
        logger.error("ESI token refresh failed: %s %s", resp.status_code, resp.text[:200])
        return None
    body = resp.json()
    token = str(body.get("access_token") or "")
    if not token:
        return None
    _access_token = token
    expires_in = body.get("expires_in")
    if expires_in is not None:
        try:
            _access_expires = datetime.now(UTC) + timedelta(seconds=int(expires_in) - 60)
        except (TypeError, ValueError):
            _access_expires = datetime.now(UTC) + timedelta(minutes=15)
    else:
        _access_expires = datetime.now(UTC) + timedelta(minutes=15)
    return token


def _standalone_refresh_configured() -> bool:
    rt = (settings.esi_refresh_token or "").strip()
    return bool(settings.esi_client_id and rt and not rt.startswith("#"))


async def bearer() -> str | None:
    global _access_token, _access_expires
    if settings.use_aa_token:
        bridged = await aa_bridge_access_token()
        if bridged:
            return bridged
        if not _standalone_refresh_configured():
            return None
    if _access_token and _access_expires and datetime.now(UTC) < _access_expires:
        return _access_token
    if not _standalone_refresh_configured():
        return None
    return await _refresh_access()


async def esi_get(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    auth: bool = True,
) -> tuple[int, Any]:
    await acquire_slot()
    headers = {"Accept": "application/json", "User-Agent": _UA}
    if auth:
        tok = await bearer()
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
    url = path if path.startswith("http") else f"{_ESI}{path}"
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.get(url, headers=headers, params=params)
    remain = resp.headers.get("X-Esi-Error-Limit-Remain")
    reset = resp.headers.get("X-Esi-Error-Limit-Reset")
    try:
        await note_error_limit(
            remain=int(remain) if remain is not None else None,
            reset=int(reset) if reset is not None else None,
        )
    except (TypeError, ValueError):
        pass
    try:
        data = resp.json()
    except Exception:
        data = None
    return resp.status_code, data


async def esi_get_paged_list(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    max_pages: int = 20,
    auth: bool = True,
) -> list[Any]:
    out: list[Any] = []
    base = dict(params or {})
    page = 1
    while page <= max_pages:
        status, data = await esi_get(path, params={**base, "page": page}, auth=auth)
        if status == 404:
            break
        if status != 200 or not isinstance(data, list):
            break
        if not data:
            break
        out.extend(data)
        if len(data) < 1000:
            break
        page += 1
    return out
