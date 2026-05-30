"""Internal HTTP API: health, resource list, paginated export."""

from __future__ import annotations

from datetime import datetime

from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from aa_report_bridge.auth import require_consumer_auth, site_id
from aa_report_bridge.exporters import list_resources, run_export
from aa_report_bridge.webhooks import build_event, deliver_event


@require_http_methods(["GET"])
def health_view(request):
    denied, consumer_id = require_consumer_auth(request)
    if denied is not None:
        return denied

    from aa_report_bridge.webhooks import _webhook_url

    return JsonResponse(
        {
            "status": "ok",
            "consumer_id": consumer_id,
            "site_id": site_id(),
            "webhook_configured": bool(_webhook_url()),
            "export_resources": [r["id"] for r in list_resources()],
        }
    )


@require_http_methods(["GET"])
def resources_view(request):
    denied, _consumer_id = require_consumer_auth(request)
    if denied is not None:
        return denied
    return JsonResponse({"resources": list_resources()})


@require_http_methods(["GET"])
def export_view(request, resource: str):
    denied, consumer_id = require_consumer_auth(request)
    if denied is not None:
        return denied

    limit_raw = request.GET.get("limit", "500").strip()
    offset_raw = request.GET.get("offset", "0").strip()
    since_raw = request.GET.get("since", "").strip()

    try:
        limit = min(max(int(limit_raw), 1), 2000)
        offset = max(int(offset_raw), 0)
    except ValueError:
        return JsonResponse({"error": "invalid_pagination"}, status=400)

    since: datetime | None = None
    if since_raw:
        since = parse_datetime(since_raw)
        if since is None:
            return JsonResponse({"error": "invalid_since", "detail": "use ISO-8601"}, status=400)

    data = run_export(resource, limit=limit, offset=offset, since=since)
    if data.get("error") == "unknown_resource":
        return JsonResponse(data, status=404)

    data["consumer_id"] = consumer_id
    data["site_id"] = site_id()
    return JsonResponse(data)


@require_http_methods(["POST"])
def webhook_test_view(request):
    """Send a test event to REPORT_BRIDGE_WEBHOOK_URL (superuser diag)."""
    denied, consumer_id = require_consumer_auth(request)
    if denied is not None:
        return denied

    event = build_event(
        action="test",
        payload={"message": "report-bridge test", "consumer_id": consumer_id},
    )
    deliver_event(event)
    return JsonResponse({"queued": True, "event_id": event["event_id"]})
