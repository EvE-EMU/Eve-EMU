"""Moon views"""

from django_datatables_view.base_datatable_view import BaseDatatableView

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import models
from django.db.models import F, Value
from django.db.models.functions import Concat
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.html import format_html

from allianceauth.eveonline.evelinks import dotlan
from app_utils.views import link_html

from metenox.models import HoldingCorporation, Metenox, Moon, Owner
from metenox.templatetags.metenox import formatisk

from ._helpers import moon_details_button_html, user_has_owner_in_corp
from .general import add_common_context


@login_required
@permission_required("metenox.view_moons")
def list_moons(request):
    """Render index view with all moons."""
    return render(request, "metenox/moons.html", add_common_context())


# pylint: disable = too-many-ancestors, duplicate-code
class MoonListJson(PermissionRequiredMixin, LoginRequiredMixin, BaseDatatableView):
    """Datatable view rendering all moons"""

    model = Moon
    permission_required = "metenox.view_moons"
    columns = [
        "id",
        "moon_name",
        "rarity_class_str",
        "solar_system_link",
        "location_html",
        "region_name",
        "constellation_name",
        "value",
        "details",
        "solar_system_name",
        "has_metenox",
    ]

    # define column names that will be used in sorting
    # order is important and should be same as order of columns
    # displayed by datatables. For non-sortable columns use empty
    # value like ''
    order_columns = [
        "eve_moon__name",
        "",
        "",
        "value",
        "",
        "",
        "",
        "",
        "",
        "",
    ]

    # pylint: disable = too-many-return-statements
    def render_column(self, row: Moon, column):
        if column == "id":
            return row.pk

        if column == "moon_name":
            return row.name

        if column == "value":
            return format_html("{}<br>{}", formatisk(row.value), formatisk(row.profit))

        if result := self._render_location(row, column):
            return result

        if column == "details":
            return self._render_details(row)
        if column == "has_metenox":
            try:
                if user_has_owner_in_corp(self.request.user, row.metenox.corporation):
                    return "YES"
            except (
                Moon.metenox.RelatedObjectDoesNotExist  # pylint: disable = no-member
            ):
                return "NO"

        return super().render_column(row, column)

    def get_initial_queryset(self):
        return self.initial_queryset()

    @classmethod
    def initial_queryset(cls):
        """Initial query"""
        moon_query = Moon.objects.select_related(
            "eve_moon",
            "eve_moon__eve_planet__eve_solar_system",
            "eve_moon__eve_planet__eve_solar_system__eve_constellation__eve_region",
            "moonmining_moon",
        ).annotate(
            rarity_class_str=Concat(
                Value("R"),
                F("moonmining_moon__rarity_class"),
                output_field=models.CharField(),
            )
        )

        return moon_query

    def filter_queryset(self, qs):
        """Use params in the GET to filter"""
        qs = self._apply_search_filter(
            qs,
            8,
            "eve_moon__eve_planet__eve_solar_system__eve_constellation__eve_region__name",
        )
        qs = self._apply_search_filter(
            qs, 7, "eve_moon__eve_planet__eve_solar_system__eve_constellation__name"
        )
        qs = self._apply_search_filter(
            qs, 5, "eve_moon__eve_planet__eve_solar_system__name"
        )
        qs = self._apply_search_filter(qs, 6, "rarity_class_str")

        # Default must be str: ``"YES" in None`` raises TypeError when DataTables omits the param.
        has_mx_filter = self.request.GET.get("columns[9][search][value]") or ""
        if "YES" in has_mx_filter:
            qs = qs.filter(metenox__isnull=False)
            if not self.request.user.has_perm("metenox.auditor"):
                user_owners = Owner.objects.filter(
                    character_ownership__user=self.request.user
                )
                user_corporations = HoldingCorporation.objects.filter(
                    owners__in=user_owners
                )
                qs = qs.filter(metenox__corporation__in=user_corporations)
        elif "NO" in has_mx_filter:
            if self.request.user.has_perm("metenox.auditor"):
                qs = qs.filter(metenox__isnull=True)
            else:
                user_owners = Owner.objects.filter(
                    character_ownership__user=self.request.user
                )
                user_corporations = HoldingCorporation.objects.filter(
                    owners__in=user_owners
                )
                user_metenoxes = Metenox.objects.filter(
                    corporation__in=user_corporations
                )
                user_metenoxes_moon_ids = user_metenoxes.values_list(
                    "moon_id", flat=True
                )
                qs = qs.exclude(eve_moon_id__in=user_metenoxes_moon_ids)

        qs = self._apply_search_filter(qs, 10, "tags__name")

        if search := self.request.GET.get("search[value]", None):
            qs = qs.filter(eve_moon__name__istartswith=search)
        return qs

    def _apply_search_filter(self, qs, column_num, field) -> models.QuerySet:
        my_filter = self.request.GET.get(f"columns[{column_num}][search][value]", None)
        if my_filter:
            if self.request.GET.get(f"columns[{column_num}][search][regex]", False):
                kwargs = {f"{field}__iregex": my_filter}
            else:
                kwargs = {f"{field}__istartswith": my_filter}
            return qs.filter(**kwargs)
        return qs

    def _render_location(self, row: Moon, column):
        solar_system = row.eve_moon.eve_planet.eve_solar_system
        if solar_system.is_high_sec:
            sec_class = "text-high-sec"
        elif solar_system.is_low_sec:
            sec_class = "text-low-sec"
        else:
            sec_class = "text-null-sec"
        solar_system_link = format_html(
            '{}&nbsp;<span class="{}">{}</span>',
            link_html(dotlan.solar_system_url(solar_system.name), solar_system.name),
            sec_class,
            round(solar_system.security_status, 1),
        )

        constellation = row.eve_moon.eve_planet.eve_solar_system.eve_constellation
        region = constellation.eve_region
        location_html = format_html(
            "{}<br><em>{}</em>", constellation.name, region.name
        )
        if column == "solar_system_name":
            return solar_system.name

        if column == "solar_system_link":
            return solar_system_link

        if column == "location_html":
            return location_html

        if column == "region_name":
            return region.name

        if column == "constellation_name":
            return constellation.name

        return None

    def _render_details(self, row):
        return moon_details_button_html(row)


@login_required
@permission_required("metenox.view_moons")
def moons_fdd_data(request) -> JsonResponse:
    """Provide lists for drop down fields"""
    qs = MoonListJson.initial_queryset()
    columns = request.GET.get("columns")
    result = {}
    if columns:
        for column in columns.split(","):
            options = [
                option for option in _calc_options(request, qs, column) if option
            ]
            result[column] = sorted(list(set(options)), key=str.casefold)
    return JsonResponse(result, safe=False)


# pylint: disable = too-many-return-statements
def _calc_options(request, qs, column):
    if column == "region_name":
        return qs.values_list(
            "eve_moon__eve_planet__eve_solar_system__eve_constellation__eve_region__name",
            flat=True,
        )

    if column == "constellation_name":
        return qs.values_list(
            "eve_moon__eve_planet__eve_solar_system__eve_constellation__name",
            flat=True,
        )

    if column == "solar_system_name":
        return qs.values_list(
            "eve_moon__eve_planet__eve_solar_system__name",
            flat=True,
        )

    if column == "rarity_class_str":
        return qs.values_list("rarity_class_str", flat=True)

    if column == "has_metenox":
        return ["YES", "NO"]

    if column == "tags":
        return qs.distinct().values_list("tags__name", flat=True)

    return [f"** ERROR: Invalid column name '{column}' **"]


@login_required
@permission_required("metenox.view_moons")
def moon_details(request, moon_pk: int):
    """Renders moon details"""
    moon = get_object_or_404(Moon, pk=moon_pk)
    context = {
        "page_title": moon.name,
        "moon": moon,
    }
    try:
        if user_has_owner_in_corp(request.user, moon.metenox.corporation):
            context["metenox"] = moon.metenox
    except Moon.metenox.RelatedObjectDoesNotExist:  # pylint: disable = no-member
        pass
    if request.GET.get("new_page"):
        context["title"] = "Moon details"
        context["content_file"] = "metenox/partials/moon_details.html"
        return render(
            request,
            "metenox/modals/generic_modal_page.html",
            add_common_context(context),
        )
    return render(
        request, "metenox/modals/moon_details.html", add_common_context(context)
    )
