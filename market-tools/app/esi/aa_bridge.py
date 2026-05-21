"""Fetch ESI access tokens from Alliance Auth (django-esi) internal bridge."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_cached_access: str | None = None
_cached_expires: datetime | None = None


async def aa_bridge_access_token() -> str | None:
    global _cached_access, _cached_expires

    if not settings.use_aa_token:
        return None
    secret = (settings.internal_secret or "").strip()
    url = (settings.aa_token_bridge_url or "").strip()
    if not secret or not url:
        return None

    if _cached_access and _cached_expires and datetime.now(UTC) < _cached_expires:
        return _cached_access

    headers = {
        "Accept": "application/json",
        "X-Market-Internal-Secret": secret,
        "User-Agent": "EVE-EMU-Market/1.0",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code != 200:
        logger.error("AA token bridge %s: %s %s", url, resp.status_code, resp.text[:200])
        return None
    body = resp.json()
    token = str(body.get("access_token") or "")
    if not token:
        return None
    _cached_access = token
    _cached_expires = datetime.now(UTC) + timedelta(minutes=15)
    logger.info(
        "AA token bridge: %s (%s)",
        body.get("character_name"),
        body.get("token_id"),
    )
    return token
