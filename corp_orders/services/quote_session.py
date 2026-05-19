from __future__ import annotations

import hashlib
import json
from typing import Any


SESSION_KEY = "corp_orders_last_quote"


def quote_fingerprint(
    *,
    items_text: str,
    speed: str,
    issuer_kind: str,
    final_destination_system: str,
) -> str:
    payload = {
        "items_text": items_text.strip(),
        "speed": speed,
        "issuer_kind": issuer_kind,
        "final_destination_system": final_destination_system.strip(),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def store_quote(request, *, fingerprint: str, quote: dict[str, Any]) -> None:
    request.session[SESSION_KEY] = {"fp": fingerprint, "quote": quote}
    request.session.modified = True


def load_quote(request, *, fingerprint: str) -> dict[str, Any] | None:
    cached = request.session.get(SESSION_KEY) or {}
    if cached.get("fp") != fingerprint:
        return None
    return cached.get("quote")
