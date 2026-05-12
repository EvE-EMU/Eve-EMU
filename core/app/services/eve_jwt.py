"""Decode EVE SSO access token JWT payload (no signature verification — obtain token via HTTPS only)."""

from __future__ import annotations

import base64
import json
from typing import Any


def decode_jwt_payload(access_token: str) -> dict[str, Any]:
    parts = access_token.split(".")
    if len(parts) != 3:
        return {}
    b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        raw = base64.urlsafe_b64decode(b64.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def character_id_from_payload(payload: dict[str, Any]) -> int | None:
    sub = str(payload.get("sub") or "")
    u = sub.upper()
    if "CHARACTER:EVE:" in u:
        tail = u.split("CHARACTER:EVE:")[-1].strip()
        if tail.isdigit():
            return int(tail)
    return None


def owner_hash_from_payload(payload: dict[str, Any]) -> str | None:
    v = payload.get("owner")
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def character_name_from_payload(payload: dict[str, Any]) -> str | None:
    name = payload.get("name")
    if name is None:
        return None
    s = str(name).strip()
    return s or None
