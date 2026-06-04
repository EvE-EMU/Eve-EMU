"""Moon Tsar UI views (AA login required)."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from moon_tsar.models import (
    MoonExtractionEvent,
    MoonHeatmapCell,
    MoonOreTaxRate,
    MoonRentalProfile,
    MoonTaxBill,
    MoonTsarSettings,
)


def _parse_date_range(request: HttpRequest) -> tuple:
    start_s = request.GET.get("start", "")
    end_s = request.GET.get("end", "")
    end = timezone.localdate()
    start = end.replace(day=1)
    if start_s:
        start = datetime.strptime(start_s, "%Y-%m-%d").date()
    if end_s:
        end = datetime.strptime(end_s, "%Y-%m-%d").date()
    return start, end


@login_required
@permission_required("moon_tsar.view_dashboard", raise_exception=True)
def dashboard(request: HttpRequest) -> HttpResponse:
    start, end = _parse_date_range(request)
    extractions = MoonExtractionEvent.objects.filter(
        popped_at__date__gte=start,
        popped_at__date__lte=end,
    ).order_by("-popped_at")[:100]
    totals = {
        "m3": sum(e.total_mined_m3 for e in extractions),
        "ore_isk": sum(e.total_ore_isk for e in extractions),
        "tax_isk": sum(e.total_tax_isk for e in extractions),
    }
    return render(
        request,
        "moon_tsar/dashboard.html",
        {
            "extractions": extractions,
            "totals": totals,
            "start": start,
            "end": end,
        },
    )


@login_required
@permission_required("moon_tsar.manage_settings", raise_exception=True)
def settings_view(request: HttpRequest) -> HttpResponse:
    cfg = MoonTsarSettings.load()
    rates = MoonOreTaxRate.objects.filter(active=True)
    return render(
        request,
        "moon_tsar/settings.html",
        {"settings": cfg, "tax_rates": rates},
    )


@login_required
@permission_required("moon_tsar.manage_settings", raise_exception=True)
@require_http_methods(["POST"])
def tax_rates_save(request: HttpRequest) -> HttpResponse:
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)
    for row in payload.get("rates", []):
        type_id = int(row["type_id"])
        MoonOreTaxRate.objects.update_or_create(
            type_id=type_id,
            defaults={
                "type_name": row.get("type_name", str(type_id))[:128],
                "tax_rate_percent": Decimal(str(row.get("tax_rate_percent", 10))),
                "use_adjusted_price": bool(row.get("use_adjusted_price", True)),
                "active": bool(row.get("active", True)),
            },
        )
    return JsonResponse({"ok": True})


@login_required
def bill_list(request: HttpRequest) -> HttpResponse:
    if request.user.has_perm("moon_tsar.view_dashboard"):
        bills = MoonTaxBill.objects.select_related("extraction", "user").order_by("-due_date")[:200]
    elif request.user.has_perm("moon_tsar.view_own_bills"):
        bills = MoonTaxBill.objects.filter(user=request.user).select_related("extraction")[:50]
    else:
        raise Http404
    return render(request, "moon_tsar/bill_list.html", {"bills": bills})


@login_required
def bill_detail(request: HttpRequest, public_id) -> HttpResponse:
    bill = get_object_or_404(MoonTaxBill, public_id=public_id)
    if bill.user_id != request.user.id and not request.user.has_perm(
        "moon_tsar.view_dashboard"
    ):
        raise Http404
    cfg = MoonTsarSettings.load()
    return render(
        request,
        "moon_tsar/bill_detail.html",
        {"bill": bill, "settings": cfg},
    )


@login_required
@permission_required("moon_tsar.view_renter_portal", raise_exception=True)
def renter_portal(request: HttpRequest) -> HttpResponse:
    profiles = MoonRentalProfile.objects.filter(active=True, renter_user=request.user)
    return render(
        request,
        "moon_tsar/renter_portal.html",
        {"profiles": profiles},
    )


@login_required
@permission_required("moon_tsar.view_dashboard", raise_exception=True)
def heatmap(request: HttpRequest) -> HttpResponse:
    start, end = _parse_date_range(request)
    cells = MoonHeatmapCell.objects.filter(
        period_start=start,
        period_end=end,
    ).order_by("-performance_score")[:500]
    return render(
        request,
        "moon_tsar/heatmap.html",
        {"cells": cells, "start": start, "end": end},
    )
