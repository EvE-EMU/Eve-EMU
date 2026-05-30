"""Push signed change events to Great Damn EMU Report (or any HTTPS consumer)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

import requests
from django.db import transaction

from aa_report_bridge.auth import site_id
from aa_report_bridge.exporters import serialize_instance

logger = logging.getLogger(__name__)


def _webhook_url() -> str:
    return os.environ.get("REPORT_BRIDGE_WEBHOOK_URL", "").strip()


def _webhook_secret() -> str:
    return os.environ.get("REPORT_BRIDGE_WEBHOOK_SECRET", "").strip()


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def build_event(*, instance=None, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if payload is None and instance is not None:
        payload = serialize_instance(instance, action=action)
    return {
        "event_id": str(uuid.uuid4()),
        "site_id": site_id(),
        "event": "aa.record.changed",
        "action": action,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload or {},
    }


def deliver_event(event: dict[str, Any], *, retries: int = 3) -> None:
    url = _webhook_url()
    secret = _webhook_secret()
    if not url:
        return
    if not secret:
        logger.warning("report_bridge: REPORT_BRIDGE_WEBHOOK_URL set but no WEBHOOK_SECRET")
        return

    body = json.dumps(event, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Report-Webhook-Signature": _sign(body, secret),
        "X-Report-Site-Id": site_id(),
        "User-Agent": "AA-Report-Bridge/0.1",
    }

    def _post() -> None:
        for attempt in range(1, retries + 1):
            try:
                resp = requests.post(url, data=body, headers=headers, timeout=15)
                if resp.status_code < 300:
                    return
                logger.warning(
                    "report_bridge webhook HTTP %s (attempt %s): %s",
                    resp.status_code,
                    attempt,
                    resp.text[:200],
                )
            except requests.RequestException as exc:
                logger.warning("report_bridge webhook failed (attempt %s): %s", attempt, exc)

    threading.Thread(target=_post, daemon=True).start()


def queue_instance_change(instance, *, action: str) -> None:
    if not _webhook_url():
        return

    def _after_commit() -> None:
        event = build_event(instance=instance, action=action)
        deliver_event(event)

    transaction.on_commit(_after_commit)
