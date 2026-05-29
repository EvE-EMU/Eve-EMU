from __future__ import annotations

import csv
import io
import json

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .reports import (
    available_report_months,
    moon_ore_report,
    user_ledger_ore_only,
    user_ore_totals_for_month,
)


def _parse_year_month(request) -> tuple[int, int]:
    today = timezone.now().date()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
    except (TypeError, ValueError):
        year, month = today.year, today.month
    month = max(1, min(12, month))
    year = max(2015, min(2100, year))
    return year, month


@login_required
@permission_required("miningtaxes.auditor_access")
def moon_ore_report_page(request):
    year, month = _parse_year_month(request)
    include_ledger = request.GET.get("include_ledger", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    report = moon_ore_report(year, month, include_character_ledger=include_ledger)
    context = {
        "page_title": "Monthly moon ore report",
        "report": report,
        "detail_json": json.dumps(report["detail"]),
        "months": available_report_months(),
        "year": year,
        "month": month,
        "include_ledger": include_ledger,
    }
    return render(request, "miningtaxes_ext/moon_ore_report.html", context)


@login_required
@permission_required("miningtaxes.auditor_access")
def moon_ore_report_json(request):
    year, month = _parse_year_month(request)
    include_ledger = request.GET.get("include_ledger", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    return JsonResponse(
        moon_ore_report(year, month, include_character_ledger=include_ledger)
    )


@login_required
@permission_required("miningtaxes.auditor_access")
def moon_ore_report_csv(request):
    year, month = _parse_year_month(request)
    include_ledger = request.GET.get("include_ledger", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    report = moon_ore_report(year, month, include_character_ledger=include_ledger)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["date", "system", "ore", "quantity", "observer", "observer_type", "source"]
    )
    for row in report["detail"]:
        writer.writerow(
            [
                row["date"],
                row["system"],
                row["ore"],
                row["quantity"],
                row["observer"],
                row["observer_type"],
                row["source"],
            ]
        )
    writer.writerow([])
    writer.writerow(["ore", "total_quantity"])
    for row in report["ore_totals"]:
        writer.writerow([row["ore"], row["quantity"]])
    response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="moon-ore-{report["month"]}.csv"'
    )
    return response


@login_required
@permission_required("miningtaxes.basic_access")
def user_ore_totals_json(request, user_pk: int):
    user = get_object_or_404(User, pk=user_pk)
    if request.user != user and not request.user.has_perm("miningtaxes.auditor_access"):
        return HttpResponseForbidden()
    year, month = _parse_year_month(request)
    return JsonResponse(user_ore_totals_for_month(user, year, month))


@login_required
@permission_required("miningtaxes.basic_access")
def user_ledger_ore_json(request, user_pk: int):
    user = get_object_or_404(User, pk=user_pk)
    if request.user != user and not request.user.has_perm("miningtaxes.auditor_access"):
        return HttpResponseForbidden()
    return JsonResponse({"data": user_ledger_ore_only(user)})
