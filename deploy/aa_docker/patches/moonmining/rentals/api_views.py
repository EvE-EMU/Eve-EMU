"""JSON API for moon rentals (OpenAPI paths under /moonmining/api/rentals/)."""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from moonmining.models import Moon

from .applications import maybe_auto_approve_application
from .forms import LeaseForm, RentalSettingsForm
from .models import MoonLease, MoonRentalApplication, RentalModuleSettings
from .structures_fuel import sync_lease_fuel_from_structures
from .services import (
    active_lease_queryset,
    available_moon_queryset,
    available_moon_to_dict,
    lease_to_dict,
    user_search_results,
)


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _require_perm(request: HttpRequest, perm: str) -> JsonResponse | None:
    if not request.user.has_perm(perm):
        return _json_error("Forbidden", 403)
    return None


@login_required
@require_http_methods(["GET", "POST"])
def api_leases(request: HttpRequest) -> JsonResponse:
    denied = _require_perm(request, "moonrentals.view_leases")
    if denied:
        return denied

    if request.method == "GET":
        admin = request.user.has_perm("moonrentals.admin_management")
        leases = [
            lease_to_dict(row, include_admin=admin)
            for row in active_lease_queryset(for_user=request.user)
        ]
        available = [
            available_moon_to_dict(m) for m in available_moon_queryset()[:500]
        ]
        return JsonResponse(
            {
                "active_leases": leases,
                "available_moons": available,
            }
        )

    denied = _require_perm(request, "moonrentals.admin_management")
    if denied:
        denied = _require_perm(request, "moonrentals.apply_rent")
        if denied:
            return denied

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON")

    moon_id = payload.get("moon_id")
    if not moon_id:
        return _json_error("moon_id required")

    try:
        moon = Moon.objects.get(pk=int(moon_id))
    except (Moon.DoesNotExist, TypeError, ValueError):
        return _json_error("Unknown moon", 404)

    if request.user.has_perm("moonrentals.admin_management"):
        lease, _created = MoonLease.objects.get_or_create(
            moon=moon,
            defaults={
                "renter_corporation": payload.get("renter_corporation", ""),
                "monthly_rent_isk": int(payload.get("monthly_rent_isk") or 0),
                "status": MoonLease.STATUS_ACTIVE,
            },
        )
        mapped = dict(payload)
        if payload.get("main_poc_id") is not None:
            mapped["main_poc_id"] = payload["main_poc_id"]
        form = LeaseForm(mapped, instance=lease)
        if not form.is_valid():
            return JsonResponse({"errors": form.errors}, status=400)
        lease = form.save()
        lease.ensure_payment_reference()
        sync_lease_fuel_from_structures(lease)
        return JsonResponse({"lease": lease_to_dict(lease, include_admin=True)})

    application = MoonRentalApplication.objects.create(
        moon=moon,
        applicant=request.user,
        renter_corporation=str(payload.get("renter_corporation", ""))[:128],
        proposed_rent_isk=int(payload.get("monthly_rent_isk") or payload.get("proposed_rent_isk") or 0),
    )
    lease = maybe_auto_approve_application(application)
    if lease:
        return JsonResponse(
            {"status": "approved", "lease": lease_to_dict(lease, include_admin=False)},
            status=201,
        )
    return JsonResponse({"status": "application_submitted"}, status=201)


@login_required
@require_http_methods(["GET", "PUT"])
def api_config(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        denied = _require_perm(request, "moonrentals.admin_management")
        if denied:
            return denied
        settings = RentalModuleSettings.load()
        return JsonResponse(
            {
                "wallet_division": settings.wallet_division,
                "keyword_match": settings.payment_keyword,
                "due_day_of_month": settings.due_day_of_month,
                "grace_period_days": settings.grace_period_days,
                "fuel_alert_threshold_percent": settings.fuel_alert_threshold_percent,
                "fuel_webhook": settings.fuel_webhook_url,
                "payment_webhook": settings.payment_webhook_url,
                "corporation_id": settings.corporation_id,
                "esi_token_id": settings.esi_token_id,
                "auto_approve_applications": settings.auto_approve_applications,
                "fuel_reference_hours": settings.fuel_reference_hours,
            }
        )

    denied = _require_perm(request, "moonrentals.admin_management")
    if denied:
        return denied

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON")

    settings = RentalModuleSettings.load()
    mapped = {
        "wallet_division": payload.get("wallet_division", settings.wallet_division),
        "payment_keyword": payload.get("keyword_match", settings.payment_keyword),
        "due_day_of_month": payload.get("due_day_of_month", settings.due_day_of_month),
        "grace_period_days": payload.get("grace_period_days", settings.grace_period_days),
        "fuel_alert_threshold_percent": payload.get(
            "fuel_alert_threshold_percent", settings.fuel_alert_threshold_percent
        ),
        "fuel_webhook_url": payload.get("fuel_webhook", settings.fuel_webhook_url),
        "payment_webhook_url": payload.get("payment_webhook", settings.payment_webhook_url),
        "corporation_id": payload.get("corporation_id", settings.corporation_id),
        "esi_token_id": payload.get("esi_token_id", settings.esi_token_id),
        "auto_approve_applications": payload.get(
            "auto_approve_applications", settings.auto_approve_applications
        ),
        "fuel_reference_hours": payload.get(
            "fuel_reference_hours", settings.fuel_reference_hours
        ),
    }
    form = RentalSettingsForm(mapped, instance=settings)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)
    form.save()
    return JsonResponse({"status": "saved"})


@login_required
@require_http_methods(["POST"])
def api_lease_evict(request: HttpRequest, lease_id: int) -> JsonResponse:
    denied = _require_perm(request, "moonrentals.admin_management")
    if denied:
        return denied
    try:
        lease = MoonLease.objects.get(pk=lease_id)
    except MoonLease.DoesNotExist:
        return _json_error("Lease not found", 404)
    lease.status = MoonLease.STATUS_EVICTED
    lease.save(update_fields=["status", "updated_at"])
    return JsonResponse({"status": "evicted"})


@login_required
@require_http_methods(["GET"])
def api_user_search(request: HttpRequest) -> JsonResponse:
    denied = _require_perm(request, "moonrentals.admin_management")
    if denied:
        return denied
    q = request.GET.get("q", "")
    return JsonResponse({"results": user_search_results(q)})
