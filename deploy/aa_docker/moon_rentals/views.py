from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from buybackprogram.models import Program

from .compliance import refresh_moon_pop_compliance
from .models import MoonPop, MoonPopMinerStatus, default_buyback_program_id
from .parsers import parse_import_text, resolve_owner


def _auditor_or_manage(request):
    return request.user.has_perm("miningtaxes.auditor_access") or request.user.has_perm(
        "moon_rentals.manage_schedule"
    )


@login_required
def schedule_list(request):
    if not _auditor_or_manage(request):
        return HttpResponseForbidden()
    pops = MoonPop.objects.select_related("private_owner").all()[:200]
    program_id = default_buyback_program_id()
    try:
        program = Program.objects.get(pk=program_id)
        program_name = program.name
    except Program.DoesNotExist:
        program_name = f"Program #{program_id}"
    return render(
        request,
        "moon_rentals/schedule.html",
        {
            "pops": pops,
            "program_id": program_id,
            "program_name": program_name,
            "buyback_url": f"/buybackprogram/program/{program_id}/calculate/",
        },
    )


@login_required
def pop_detail(request, pop_id: int):
    if not _auditor_or_manage(request):
        return HttpResponseForbidden()
    moon_pop = get_object_or_404(MoonPop.objects.select_related("private_owner"), pk=pop_id)
    miners = list(moon_pop.miner_statuses.select_related("user").all())
    if request.GET.get("refresh") == "1":
        miners = refresh_moon_pop_compliance(moon_pop)
        messages.success(request, "Compliance data refreshed from mining logs and buyback.")
        return redirect("moon_rentals:pop_detail", pop_id=pop_id)
    return render(
        request,
        "moon_rentals/pop_detail.html",
        {
            "moon_pop": moon_pop,
            "miners": miners,
            "buyback_url": moon_pop.buyback_calculate_url_path,
        },
    )


@login_required
@require_POST
def pop_refresh(request, pop_id: int):
    if not _auditor_or_manage(request):
        return HttpResponseForbidden()
    moon_pop = get_object_or_404(MoonPop, pk=pop_id)
    refresh_moon_pop_compliance(moon_pop)
    messages.success(request, "Compliance refreshed.")
    return redirect("moon_rentals:pop_detail", pop_id=pop_id)


@login_required
def import_page(request):
    if not request.user.has_perm("moon_rentals.manage_schedule") and not request.user.has_perm(
        "miningtaxes.admin_access"
    ):
        if not _auditor_or_manage(request):
            return HttpResponseForbidden()

    results = []
    if request.method == "POST":
        text = request.POST.get("paste", "")
        default_kind = request.POST.get(
            "default_kind", MoonPop.CORP_FALSE_GODS
        )
        default_owner = request.POST.get("default_owner", "").strip() or None
        program_id = request.POST.get("program_id", "").strip()
        try:
            program_id = int(program_id) if program_id else default_buyback_program_id()
        except ValueError:
            program_id = default_buyback_program_id()

        created = 0
        skipped = 0
        errors: list[str] = []

        for row in parse_import_text(
            text,
            default_kind=default_kind,
            default_owner_username=default_owner,
        ):
            owner = resolve_owner(row.private_owner_username)
            if row.rental_kind == MoonPop.PRIVATE and owner is None:
                errors.append(
                    f"Line {row.line_no}: private moon needs user "
                    f"{row.private_owner_username!r} on Auth"
                )
                skipped += 1
                continue
            _, was_created = MoonPop.objects.get_or_create(
                location_label=row.location_label,
                pop_at=row.pop_at,
                defaults={
                    "system_name": row.system_name,
                    "moon_number": row.moon_number,
                    "rental_kind": row.rental_kind,
                    "private_owner": owner,
                    "buyback_program_id": program_id,
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1
            results.append(row)

        if created:
            messages.success(request, f"Imported {created} moon pop(s).")
        if errors:
            messages.warning(request, "; ".join(errors[:5]))
        if skipped and not errors:
            messages.info(request, f"Skipped {skipped} duplicate or empty line(s).")

        if request.POST.get("redirect") == "list":
            return redirect("moon_rentals:schedule")

    return render(
        request,
        "moon_rentals/import.html",
        {
            "default_program_id": default_buyback_program_id(),
            "results": results,
        },
    )


@login_required
def import_example_json(request):
    """Return example paste format for the UI."""
    return JsonResponse(
        {
            "example": (
                "# Tab-separated: location<TAB>datetime  (optional |username for private)\n"
                "9SBB-9 VII - Moon 20\t5/28/2026 19:00:00|sevey\n"
                "TV8-HS VII - Moon 4\t6/2/2026 20:00:00\n"
                "RF-CN3 V - Moon 10\t6/6/2026 20:00:00\n"
            )
        }
    )
