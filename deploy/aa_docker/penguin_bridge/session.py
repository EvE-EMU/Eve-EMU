"""Stateless signed session token for the EVE-Penguin desktop client.

Mirrors the freight handoff session: base64url(JSON payload) + "." +
base64url(HMAC-SHA256(SECRET_KEY, payload)). No DB row, so deploying is just a
container restart. Logout is client-side (drop the token); tokens are short-TTL.
A DB-backed revocation list can be layered on later without changing the wire
format.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from django.conf import settings

# 30 days. The desktop app silently re-runs the browser login when /penguin/me
# starts returning 401.
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60


def _secret() -> bytes:
    return (settings.SECRET_KEY or "penguin-dev").encode("utf-8")


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(txt: str) -> bytes:
    pad = "=" * (-len(txt) % 4)
    return base64.urlsafe_b64decode(txt + pad)


def issue(user, *, main_character_id: int = 0) -> str:
    now = int(time.time())
    payload = {
        "uid": int(user.pk),
        "uname": user.username,
        "main": int(main_character_id or 0),
        "iat": now,
        "exp": now + SESSION_TTL_SECONDS,
    }
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _b64e(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    body, _, sig = token.partition(".")
    expected = _b64e(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(_b64d(body))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload
