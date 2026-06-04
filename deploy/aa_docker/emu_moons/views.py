"""EMU Moons UI — extends moonmining data without replacing it."""

from __future__ import annotations

import csv
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from emu_moons.access import (
    can_view_all_accounts,
    can_view_alliance_dashboard,
    can_view_corp_dashboard,
    can_view_invoice,
    can_view_own_statement,
    can_view_user_statement,
    tax_effective_date,
    user_corp_id,
)
from emu_moons.models import EmuInvoice, EmuMoonsSettings, StructureClass, StructureTaxProfile
from emu_moons.services.account_statement import build_account_statement, wallet_reason_for_user
from emu_moons.services.alliance_reporting import build_alliance_dashboard_context
from emu_moons.services.scheduling import _structure_class, _system_name


def index(request):
    return redirect("emu_moons:naughty_list")


def _active_invoice_qs():
    cutoff = tax_effective_date()
    return (
        EmuInvoice.objects.exclude(status=EmuInvoice.STATUS_VOID)
        .filter(due_at__gte=cutoff, issued_at__date__gte=cutoff)
    )


def _invoice_queryset_for_request(request):
    qs = _active_invoice_qs().select_related("extraction", "user").order_by("-issued_at")
    if can_view_alliance_dashboard(request.user):
        return qs
    if can_view_corp_dashboard(request.user):
        corp_id = user_corp_id(request.user)
        if corp_id:
            return qs.filter(corporation_id=corp_id)
    if can_view_own_statement(request.user):
        return qs.filter(user=request.user)
    return None


def _accounts_from_invoices(invoices) -> list[dict]:
    from collections import defaultdict

    by_user: dict[int, list[EmuInvoice]] = defaultdict(list)
    for inv in invoices:
        by_user[inv.user_id].append(inv)

    accounts = []
    for invs in by_user.values():
        user = invs[0].user
        open_invs = [
            i
            for i in invs
            if i.status
            in (
                EmuInvoice.STATUS_OPEN,
                EmuInvoice.STATUS_PARTIAL,
                EmuInvoice.STATUS_CORP_LIABLE,
            )
        ]
        total_due = sum((i.total_due_isk for i in open_invs), Decimal("0"))
        accounts.append(
            {
                "user": user,
                "username": user.username,
                "wallet_reason": wallet_reason_for_user(user),
                "invoice_count": len(open_invs),
                "character_names": sorted({i.character_name for i in open_invs if i.character_name}),
                "total_due_isk": total_due,
                "on_naughty": any(i.on_naughty_list for i in open_invs),
            }
        )
    accounts.sort(key=lambda row: row["total_due_isk"], reverse=True)
    return accounts


@login_required
def invoice_list(request):
    if not can_view_all_accounts(request.user):
        return HttpResponseForbidden()
    qs = _invoice_queryset_for_request(request)
    if qs is None:
        return HttpResponseForbidden()
    accounts = _accounts_from_invoices(list(qs[:500]))
    return render(
        request,
        "emu_moons/invoice_list.html",
        {"accounts": accounts, "page_title": _("Invoices")},
    )


@login_required
def account_statement(request, username: str | None = None):
    if username:
        target = get_object_or_404(User, username__iexact=username)
    else:
        target = request.user

    if not can_view_user_statement(request.user, target):
        return HttpResponseForbidden()

    highlight = request.GET.get("invoice", "").strip() or None
    statement = build_account_statement(target, highlight_invoice_number=highlight)
    return render(
        request,
        "emu_moons/account_statement.html",
        {"statement": statement, "page_title": _("Account Statement")},
    )


@login_required
def invoice_detail(request, invoice_number: str):
    inv = get_object_or_404(
        EmuInvoice.objects.select_related("extraction", "user"),
        invoice_number__iexact=invoice_number,
    )
    if not can_view_invoice(request.user, inv):
        return HttpResponseForbidden()
    statement = build_account_statement(
        inv.user, highlight_invoice_number=invoice_number
    )
    return render(
        request,
        "emu_moons/account_statement.html",
        {"statement": statement, "page_title": _("Account Statement")},
    )


def naughty_list(request):
    cfg = EmuMoonsSettings.load()
    invoices = [
        inv
        for inv in EmuInvoice.objects.select_related("extraction", "user")
        .order_by("-due_at")[:500]
        if inv.on_naughty_list
    ]
    if request.GET.get("format") == "csv":
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="emu_moons_naughty_list.csv"'
        w = csv.writer(resp)
        w.writerow(
            [
                "character",
                "corporation",
                "invoice",
                "original_tax",
                "penalty",
                "total_due",
                "days_overdue",
            ]
        )
        for inv in invoices:
            w.writerow(
                [
                    inv.character_name,
                    inv.corporation_name,
                    inv.invoice_number,
                    inv.original_tax_isk,
                    inv.penalty_isk,
                    inv.total_due_isk,
                    inv.days_overdue,
                ]
            )
        return resp
    return render(
        request,
        "emu_moons/naughty_list.html",
        {
            "invoices": invoices,
            "grace_days": cfg.grace_days_before_penalty,
            "tax_effective_date": cfg.tax_effective_date,
            "page_title": _("Naughty List"),
        },
    )


@login_required
def alliance_dashboard(request):
    if not can_view_alliance_dashboard(request.user):
        return HttpResponseForbidden()
    try:
        ctx = build_alliance_dashboard_context()
    except Exception:
        import logging

        logging.getLogger(__name__).exception("emu_moons alliance dashboard failed")
        ctx = {
            "kpi_all_time": {
                "tax_generated": Decimal("0"),
                "tax_collected": Decimal("0"),
                "volume_m3": Decimal("0"),
                "invoice_count": 0,
                "outstanding": Decimal("0"),
                "open_count": 0,
            },
            "kpi_month": {
                "tax_generated": Decimal("0"),
                "tax_collected": Decimal("0"),
                "volume_m3": Decimal("0"),
                "invoice_count": 0,
                "outstanding": Decimal("0"),
                "open_count": 0,
            },
            "kpi_year": {
                "tax_generated": Decimal("0"),
                "tax_collected": Decimal("0"),
                "volume_m3": Decimal("0"),
                "invoice_count": 0,
                "outstanding": Decimal("0"),
                "open_count": 0,
            },
            "period_month_label": "",
            "period_year_label": "",
            "leaderboards": {
                key: []
                for key in (
                    "corp_volume",
                    "corp_tax_paid",
                    "corp_outstanding",
                    "user_volume",
                    "user_tax_paid",
                    "user_outstanding",
                )
            },
            "dashboard_error": True,
        }
    ctx["page_title"] = _("Alliance")
    ctx["tax_effective_date"] = tax_effective_date()
    return render(request, "emu_moons/alliance_dashboard.html", ctx)


@login_required
def corp_dashboard(request):
    if not can_view_corp_dashboard(request.user):
        return HttpResponseForbidden()
    corp_id = user_corp_id(request.user)
    if not corp_id:
        return HttpResponseForbidden()
    qs = _active_invoice_qs().filter(corporation_id=corp_id)
    outstanding = sum(inv.total_due_isk for inv in qs.filter(status=EmuInvoice.STATUS_OPEN)[:200])
    return render(
        request,
        "emu_moons/corp_dashboard.html",
        {
            "invoices": qs.order_by("-issued_at")[:100],
            "outstanding": outstanding,
            "page_title": _("Corporation"),
        },
    )


def _refinery_rows_for_admin():
    try:
        from moonmining.models import Refinery
    except ImportError:
        return []
    profiles = {
        p.moonmining_refinery_id: p
        for p in StructureTaxProfile.objects.select_related("private_owner").exclude(
            moonmining_refinery_id__isnull=True
        )
    }
    rows = []
    for ref in Refinery.objects.select_related("moon").order_by("name"):
        prof = profiles.get(ref.pk)
        sclass = prof.structure_class if prof else _structure_class(ref.pk, ref.name or "")
        rows.append(
            {
                "refinery_id": ref.pk,
                "name": ref.name or str(ref.moon or ref.pk),
                "system_name": _system_name(ref),
                "structure_class": sclass,
                "structure_class_display": dict(StructureClass.choices).get(sclass, sclass),
                "private_owner": prof.private_owner if prof else None,
                "profile": prof,
            }
        )
    return rows


@login_required
@permission_required("emu_moons.emu_moons_admin", raise_exception=True)
@require_http_methods(["GET", "POST"])
def admin_settings(request):
    cfg = EmuMoonsSettings.load()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "assign_private_owner":
            refinery_id = request.POST.get("refinery_id")
            owner_id = request.POST.get("owner_id") or ""
            try:
                refinery_id = int(refinery_id)
            except (TypeError, ValueError):
                messages.error(request, _("Invalid refinery."))
                return redirect("emu_moons:admin_settings")
            try:
                from moonmining.models import Refinery

                refinery = Refinery.objects.get(pk=refinery_id)
            except Exception:
                messages.error(request, _("Refinery not found."))
                return redirect("emu_moons:admin_settings")

            owner = None
            if owner_id:
                try:
                    owner = User.objects.get(pk=int(owner_id), is_active=True)
                except (User.DoesNotExist, ValueError):
                    messages.error(request, _("User not found."))
                    return redirect("emu_moons:admin_settings")

            prof, _created = StructureTaxProfile.objects.get_or_create(
                moonmining_refinery_id=refinery.pk,
                defaults={
                    "structure_name": refinery.name or str(refinery),
                    "system_name": _system_name(refinery),
                    "structure_class": StructureClass.PRIVATE
                    if owner
                    else _structure_class(refinery.pk, refinery.name or ""),
                },
            )
            prof.structure_name = refinery.name or prof.structure_name
            prof.system_name = _system_name(refinery) or prof.system_name
            prof.private_owner = owner
            if owner:
                prof.structure_class = StructureClass.PRIVATE
            prof.save()
            if owner:
                messages.success(
                    request,
                    _("Assigned %(user)s to %(moon)s.")
                    % {"user": owner.username, "moon": prof.structure_name},
                )
            else:
                messages.success(request, _("Cleared private owner for %(moon)s.") % {"moon": prof.structure_name})
        return redirect("emu_moons:admin_settings")

    structures = StructureTaxProfile.objects.select_related("private_owner").all()
    refinery_rows = _refinery_rows_for_admin()
    users = User.objects.filter(is_active=True).order_by("username")[:500]
    return render(
        request,
        "emu_moons/admin_settings.html",
        {
            "settings": cfg,
            "structures": structures,
            "refinery_rows": refinery_rows,
            "users": users,
            "page_title": _("Admin"),
        },
    )
