"""Verify signed webhooks from aa-report-bridge."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from fastapi import HTTPException, Request

from report_app.connections import AaLink, get_link
from report_app.history import insert_event


def _link_ingest_secret(link: AaLink) -> str:
    return (link.webhook_secret or link.bridge_secret or link.secret).strip()


def verify_signature(body: bytes, signature_header: str | None, secret: str) -> bool:
    if not signature_header or not secret:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header.strip())


async def ingest_webhook(link_id: str, request: Request) -> dict[str, Any]:
    link = get_link(link_id)
    if link is None:
        raise HTTPException(404, f"unknown link {link_id!r}")

    body = await request.body()
    sig = request.headers.get("X-Report-Webhook-Signature")
    secret = _link_ingest_secret(link)
    if not secret:
        raise HTTPException(503, "link has no webhook_secret configured")
    if not verify_signature(body, sig, secret):
        raise HTTPException(403, "invalid webhook signature")

    try:
        event = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "invalid JSON") from exc

    payload = event.get("payload") or {}
    model = payload.get("model") if isinstance(payload, dict) else None
    action = event.get("action") or (payload.get("action") if isinstance(payload, dict) else None)

    row_id = insert_event(
        link_id,
        event_id=event.get("event_id"),
        site_id=event.get("site_id") or request.headers.get("X-Report-Site-Id"),
        event_type=event.get("event", "aa.record.changed"),
        action=action,
        model=model,
        occurred_at=event.get("occurred_at"),
        payload=event if isinstance(event, dict) else {"raw": event},
        source="webhook",
    )
    return {"stored": True, "id": row_id, "event_id": event.get("event_id")}
