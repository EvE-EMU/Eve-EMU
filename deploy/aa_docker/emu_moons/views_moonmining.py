"""Extend moonmining extractions page with EMU Moons scheduling assistant."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.db.models import F
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from emu_moons.models import StructureClass
from emu_moons.services.calendar import (
    calendar_events_for_user,
    user_can_access_calendar,
    user_owns_private_refinery_ids,
)
from emu_moons.services.moonmining_reports import tracked_refinery_ids
from emu_moons.services.scheduling import scheduling_rows_for_moonmining

EMU_MOONS_TAB_NEXT = "next"
_SORT_MIN = datetime(1970, 1, 1, tzinfo=timezone.utc)

_CLASS_BADGE = {
    StructureClass.PUBLIC: "primary",
    StructureClass.NATIONALIZED: "warning",
    StructureClass.PRIVATE: "secondary",
}


def _can_view_scheduling(user) -> bool:
    return user.has_perm("emu_moons.emu_moons_admin") or user.has_perm(
        "emu_moons.emu_moons_view_alliance"
    )


def _class_badge_html(structure_class: str, label: str) -> str:
    css = _CLASS_BADGE.get(structure_class, "primary")
    return format_html('<span class="badge text-bg-{}">{}</span>', css, label)


def _format_dt_cell(when, *, badge_html: str = "", strong: bool = True) -> dict:
    from moonmining.constants import DATETIME_FORMAT

    if not when:
        return {"display": "—", "sort": _SORT_MIN}
    dt_str = timezone.localtime(when).strftime(DATETIME_FORMAT)
    if badge_html:
        line = format_html("<strong>{}</strong>", dt_str) if strong else dt_str
        display = format_html("{}<br>{}", line, badge_html)
    elif strong:
        display = format_html("<strong>{}</strong>", dt_str)
    else:
        display = dt_str
    return {"display": display, "sort": when}


@login_required
@permission_required(["moonmining.extractions_access", "moonmining.basic_access"])
def extractions(request):
    from moonmining.app_settings import (
        MOONMINING_COMPLETED_EXTRACTIONS_HOURS_UNTIL_STALE,
        MOONMINING_REPROCESSING_YIELD,
        MOONMINING_USE_REPROCESS_PRICING,
        MOONMINING_VOLUME_PER_MONTH,
    )
    from moonmining.models import Extraction
    from moonmining.views.extractions import ExtractionsCategory

    can_schedule = _can_view_scheduling(request.user)
    context = {
        "page_title": _("Extractions"),
        "ExtractionsCategory": ExtractionsCategory.to_dict(),
        "ExtractionsStatus": Extraction.Status,
        "use_reprocess_pricing": MOONMINING_USE_REPROCESS_PRICING,
        "reprocessing_yield": MOONMINING_REPROCESSING_YIELD * 100,
        "total_volume_per_month": MOONMINING_VOLUME_PER_MONTH / 1000000,
        "stale_hours": MOONMINING_COMPLETED_EXTRACTIONS_HOURS_UNTIL_STALE,
        "emu_moons_show_scheduling": can_schedule,
        "EmuMoonsTabNext": EMU_MOONS_TAB_NEXT,
    }
    try:
        from moonmining_discord_events import discord_sync_configured

        context["moonmining_discord_sync_enabled"] = discord_sync_configured()
    except ImportError:
        context["moonmining_discord_sync_enabled"] = False
    return render(request, "moonmining/extractions.html", context)


@login_required
@permission_required(["moonmining.extractions_access", "moonmining.basic_access"])
@require_POST
def sync_discord_events(request):
    """Create missing Discord guild scheduled events for upcoming extractions."""
    try:
        from moonmining_discord_events import sync_extractions_to_discord
    except ImportError as exc:
        messages.error(request, _("Discord sync module is not installed: %s") % exc)
        return redirect("moonmining:extractions")

    try:
        result = sync_extractions_to_discord(dry_run=False)
    except RuntimeError as exc:
        messages.error(request, str(exc))
        return redirect("moonmining:extractions")
    except Exception as exc:
        messages.error(request, _("Discord sync failed: %s") % exc)
        return redirect("moonmining:extractions")

    if result.errors:
        messages.warning(
            request,
            _(
                "Discord sync finished: %(created)s created, %(skipped)s already on calendar, "
                "%(errors)s error(s) (%(examined)s extractions checked)."
            )
            % {
                "created": result.created,
                "skipped": result.skipped,
                "errors": result.errors,
                "examined": result.examined,
            },
        )
    else:
        messages.success(
            request,
            _(
                "Discord sync finished: %(created)s created, %(skipped)s already on calendar "
                "(%(examined)s extractions checked)."
            )
            % {
                "created": result.created,
                "skipped": result.skipped,
                "examined": result.examined,
            },
        )
    return redirect("moonmining:extractions")


@login_required
@permission_required(["moonmining.extractions_access", "moonmining.basic_access"])
def next_extractions_data(request: HttpRequest) -> JsonResponse:
    if not _can_view_scheduling(request.user):
        return JsonResponse([], safe=False)

    from allianceauth.eveonline.evelinks import dotlan
    from app_utils.views import link_html
    from moonmining.views._helpers import moon_details_button_html
    from moonmining.views.extractions import extraction_details_button_html

    data = []
    for row in scheduling_rows_for_moonmining():
        refinery = row["refinery"]
        moon = getattr(refinery, "moon", None)
        moon_name = row.get("moon_name") or row["structure_name"]
        class_badge = _class_badge_html(
            row["structure_class"], row["structure_class_display"]
        )

        refinery_html = {"display": row["structure_name"], "sort": row["structure_name"]}
        try:
            refinery_html = {
                "display": refinery.name_html(),
                "sort": str(refinery.name or row["structure_name"]),
            }
        except Exception:
            corp = row.get("corporation_name") or ""
            if corp:
                refinery_html["display"] = format_html(
                    "{}<br>{}", row["structure_name"], corp
                )

        location_html = row.get("system_name") or "—"
        location_sort = row.get("system_name") or ""
        try:
            if moon and moon.eve_moon_id:
                solar = moon.eve_moon.eve_planet.eve_solar_system
                location_html = format_html(
                    "{}<br><i>{}</i>",
                    link_html(dotlan.solar_system_url(solar.name), moon_name),
                    solar.eve_constellation.eve_region.name,
                )
                location_sort = moon_name
        except Exception:
            region = row.get("region_name") or ""
            if region and row.get("system_name"):
                location_html = format_html(
                    "{}<br><i>{}</i>",
                    row["system_name"],
                    region,
                )

        labels_html = ""
        if moon:
            try:
                labels_html = moon.labels_html()
            except Exception:
                pass

        details_html = ""
        if row.get("last_extraction_id"):
            details_html += extraction_details_button_html(row["last_extraction_id"])
        if moon:
            if details_html:
                details_html += "&nbsp;"
            details_html += moon_details_button_html(moon)

        suggested_cell = _format_dt_cell(row["suggested_at"], badge_html=class_badge)
        last_cell = _format_dt_cell(row.get("last_pop"), strong=False)

        data.append(
            {
                "chunk_arrival_at": suggested_cell,
                "refinery": refinery_html,
                "location": {"display": location_html, "sort": location_sort},
                "labels": labels_html,
                "last_scheduled": last_cell,
                "volume": "",
                "value": "",
                "mined_value": "",
                "details": details_html,
                "corporation_name": row.get("corporation_name") or "",
                "alliance_name": row.get("alliance_name") or "",
                "status_str": row["structure_class_display"],
                "moon_name": moon_name,
                "region_name": row.get("region_name") or "",
                "constellation_name": row.get("constellation_name") or "",
                "rarity_class": row.get("rarity_class") or "",
            }
        )
    return JsonResponse(data, safe=False)


def _parse_calendar_range(request: HttpRequest) -> tuple[datetime | None, datetime | None]:
    from django.utils.dateparse import parse_datetime

    start_s = request.GET.get("start")
    end_s = request.GET.get("end")
    start = parse_datetime(start_s.replace("Z", "+00:00")) if start_s else None
    end = parse_datetime(end_s.replace("Z", "+00:00")) if end_s else None
    if start and timezone.is_naive(start):
        start = timezone.make_aware(start)
    if end and timezone.is_naive(end):
        end = timezone.make_aware(end)
    return start, end


@login_required
def calendar(request: HttpRequest):
    if not user_can_access_calendar(request.user):
        return HttpResponseForbidden()
    show_suggested = request.user.has_perm("moonmining.extractions_access") or bool(
        user_owns_private_refinery_ids(request.user)
    )
    return render(
        request,
        "moonmining/calendar.html",
        {
            "page_title": _("Moon calendar"),
            "show_suggested": show_suggested,
            "is_private_only": not request.user.has_perm("moonmining.extractions_access"),
        },
    )


@login_required
@require_GET
def calendar_events(request: HttpRequest) -> JsonResponse:
    if not user_can_access_calendar(request.user):
        return JsonResponse({"error": "forbidden"}, status=403)
    range_start, range_end = _parse_calendar_range(request)
    include_suggested = request.GET.get("suggested", "1") != "0"
    events = calendar_events_for_user(
        request.user,
        range_start=range_start,
        range_end=range_end,
        include_suggested=include_suggested,
    )
    return JsonResponse(events, safe=False)


def _default_if_false(value, default):
    if not value:
        return default
    return value


def _report_month_bounds(today: dt.datetime):
    months_1 = today.replace(day=1) - dt.timedelta(days=1)
    months_2 = months_1.replace(day=1) - dt.timedelta(days=1)
    months_3 = months_2.replace(day=1) - dt.timedelta(days=1)
    return today, months_1, months_2, months_3


def _member_mining_user_row(user, volumes: dict[int, float], prices: dict[int, float]) -> dict:
    corporation_name = user.profile.main_character.corporation_name
    if user.profile.main_character.alliance_ticker:
        corporation_name += f" [{user.profile.main_character.alliance_ticker}]"
    return {
        "id": user.id,
        "name": str(user.profile.main_character),
        "corporation": corporation_name,
        "state": str(user.profile.state),
        "volume_month_0": _default_if_false(volumes.get(0), 0),
        "volume_month_1": _default_if_false(volumes.get(1), 0),
        "volume_month_2": _default_if_false(volumes.get(2), 0),
        "volume_month_3": _default_if_false(volumes.get(3), 0),
        "price_month_0": _default_if_false(prices.get(0), 0),
        "price_month_1": _default_if_false(prices.get(1), 0),
        "price_month_2": _default_if_false(prices.get(2), 0),
        "price_month_3": _default_if_false(prices.get(3), 0),
    }


def _character_ledger_member_mining_rows() -> list[dict]:
    """Personal miningtaxes ledgers in moon systems (last four calendar months)."""
    try:
        from django.db.models import F
        from django.db.models.functions import Coalesce

        from miningtaxes.models import CharacterMiningLedgerEntry
    except ImportError:
        return []

    from emu_moons.services.moonmining_reports import _refinery_by_system_name

    system_names = set(_refinery_by_system_name().keys())
    if not system_names:
        return []

    today, months_1, months_2, months_3 = _report_month_bounds(timezone.now())
    month_keys = [
        (today.year, today.month),
        (months_1.year, months_1.month),
        (months_2.year, months_2.month),
        (months_3.year, months_3.month),
    ]
    oldest = month_keys[-1]

    qs = (
        CharacterMiningLedgerEntry.objects.filter(
            date__gte=dt.date(oldest[0], oldest[1], 1),
        )
        .annotate(
            user_id=F("character__eve_character__character_ownership__user_id"),
            ore_volume=Coalesce(F("eve_type__volume"), 0.0),
            line_value=Coalesce(F("taxed_value"), 0.0),
        )
        .filter(user_id__isnull=False)
        .values(
            "user_id",
            "date",
            "quantity",
            "ore_volume",
            "line_value",
            system_name=F("eve_solar_system__name"),
        )
    )

    user_vol: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    user_price: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))

    for row in qs.iterator(chunk_size=4000):
        if (row["system_name"] or "").upper() not in system_names:
            continue
        user_id = row["user_id"]
        d = row["date"]
        idx = None
        for i, (y, m) in enumerate(month_keys):
            if d.year == y and d.month == m:
                idx = i
                break
        if idx is None:
            continue
        qty = float(row["quantity"] or 0)
        user_vol[user_id][idx] += qty * float(row["ore_volume"] or 0)
        user_price[user_id][idx] += float(row["line_value"] or 0)

    if not user_vol:
        return []

    users = User.objects.filter(
        pk__in=user_vol.keys(), profile__main_character__isnull=False
    ).select_related("profile__main_character", "profile__state")

    data = []
    for user in users:
        vols = user_vol.get(user.pk, {})
        if not any(vols.get(i) for i in range(4)):
            continue
        data.append(_member_mining_user_row(user, vols, user_price.get(user.pk, {})))
    return data


def _miningtaxes_member_mining_rows() -> list[dict]:
    """Corp moon observer logs by AA user (non-private structures only)."""
    try:
        from allianceauth.eveonline.models import CharacterOwnership
        from miningtaxes.helpers import PriceGroups
        from miningtaxes.models import AdminMiningObsLog
    except ImportError:
        return []

    tracked = tracked_refinery_ids()
    if not tracked:
        return []

    today, months_1, months_2, months_3 = _report_month_bounds(timezone.now())
    month_keys = [
        (today.year, today.month),
        (months_1.year, months_1.month),
        (months_2.year, months_2.month),
        (months_3.year, months_3.month),
    ]

    miner_to_user = dict(
        CharacterOwnership.objects.values_list("character__character_id", "user_id")
    )
    qs = AdminMiningObsLog.objects.filter(
        observer__obs_id__in=tracked,
        eve_type__group_id__in=PriceGroups.moon_ore_groups,
    ).values(
        "miner_id",
        "date",
        "quantity",
        ore_volume=Coalesce(F("eve_type__volume"), 0.0),
    )

    user_vol: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    user_price: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))

    for row in qs.iterator(chunk_size=2000):
        user_id = miner_to_user.get(row["miner_id"])
        if not user_id:
            continue
        d = row["date"]
        idx = None
        for i, (y, m) in enumerate(month_keys):
            if d.year == y and d.month == m:
                idx = i
                break
        if idx is None:
            continue
        qty = float(row["quantity"] or 0)
        user_vol[user_id][idx] += qty * float(row["ore_volume"] or 0)

    if not user_vol:
        return []

    users = User.objects.filter(
        pk__in=user_vol.keys(), profile__main_character__isnull=False
    ).select_related("profile__main_character", "profile__state")

    data = []
    for user in users:
        vols = user_vol.get(user.pk, {})
        if not any(vols.get(i) for i in range(4)):
            continue
        data.append(_member_mining_user_row(user, vols, user_price.get(user.pk, {})))
    return data


@login_required()
@permission_required(["moonmining.basic_access", "moonmining.reports_access"])
def report_user_mining_data(request):
    """Member Mining tab — moonmining ledger, then miningtaxes observer fallback."""
    from moonmining.views.reports import report_user_mining_data as stock_report

    response = stock_report(request)
    try:
        import json

        data = json.loads(response.content)
    except Exception:
        data = []

    if data:
        return response

    for builder in (_miningtaxes_member_mining_rows, _character_ledger_member_mining_rows):
        rows = builder()
        if rows:
            return JsonResponse(rows, safe=False)
    return JsonResponse([], safe=False)
