"""Signed browser session tokens for EMUMS SSO."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.config import settings


def _secret() -> bytes:
    raw = (settings.session_secret or settings.api_key or "emums-dev").encode()
    return raw


def create_session_token(character_id: int, *, ttl_seconds: int | None = None) -> str:
    ttl = ttl_seconds if ttl_seconds is not None else settings.session_ttl_seconds
    payload = {"cid": int(character_id), "exp": int(time.time()) + int(ttl)}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def parse_session_token(token: str | None) -> int | None:
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    expected = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    pad = "=" * (-len(body) % 4)
    try:
        payload: dict[str, Any] = json.loads(base64.urlsafe_b64decode((body + pad).encode()))
    except (ValueError, json.JSONDecodeError):
        return None
    exp = int(payload.get("exp") or 0)
    if exp < int(time.time()):
        return None
    cid = payload.get("cid")
    if cid is None:
        return None
    try:
        return int(cid)
    except (TypeError, ValueError):
        return None
