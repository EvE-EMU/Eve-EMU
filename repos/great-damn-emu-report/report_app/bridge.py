"""Pull historical snapshots from aa-report-bridge on each linked AA."""

from __future__ import annotations

from typing import Any

from report_bridge_client import ReportBridgeClient

from report_app.connections import AaLink, get_link
from report_app.history import insert_event


def bridge_client_for(link: AaLink) -> ReportBridgeClient:
    secret = (link.bridge_secret or link.secret).strip()
    return ReportBridgeClient(
        base_url=link.forwarder_url.rstrip("/"),
        secret=secret,
        user_agent="GreatDamnEMUReport/1.0",
    )


def test_bridge(link: AaLink) -> dict[str, Any]:
    return bridge_client_for(link).ping()


def sync_export(
    link_id: str,
    resource: str,
    *,
    page_size: int = 500,
    since_iso: str | None = None,
) -> dict[str, Any]:
    link = get_link(link_id)
    if link is None:
        raise KeyError(f"unknown link: {link_id}")

    from datetime import datetime

    since = datetime.fromisoformat(since_iso) if since_iso else None
    client = bridge_client_for(link)
    stored = 0
    for row in client.export_all(resource, page_size=page_size, since=since):
        insert_event(
            link_id,
            event_id=None,
            site_id=None,
            event_type="aa.export.snapshot",
            action="snapshot",
            model=resource,
            occurred_at=None,
            payload={"resource": resource, "record": row},
            source="export",
        )
        stored += 1
    return {"link_id": link_id, "resource": resource, "stored": stored}
