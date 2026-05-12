"""EVE Online SSO HTTP: authorization code and refresh token grants."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from app.config import settings


def _basic_auth_header() -> str:
    raw = f"{settings.sso_client_id}:{settings.sso_client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


async def exchange_authorization_code(*, code: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            settings.sso_token_url,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.sso_callback_url,
            },
        )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}


async def refresh_access_token(*, refresh_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            settings.sso_token_url,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}
