"""Views for rending blueprint lists for Blueprints."""

from typing import Any

from dj_datatables_view.base_datatable_view import BaseDatatableView

from django.utils.html import format_html
from django.utils.translation import gettext_lazy
from eveuniverse.models import EveType

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from blueprints import __title__
from blueprints.app_settings import BLUEPRINTS_LIST_ICON_OUTPUT_SIZE
from blueprints.models import Blueprint

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


# pylint: disable = too-many-ancestors
class BlueprintListJson(BaseDatatableView):
    """View for creating a list view of blueprints for datatables."""

    # The model we're going to show
    model = Blueprint

    # define the columns that will be returned
    columns = [
        "eve_type_icon",
        "eve_type",
        "quantity",
        "owner",
        "material_efficiency",
        "time_efficiency",
        "is_original",
        "runs",
        "pk",
        "location",
        "industryjob",
    ]

    # define column names that will be used in sorting
    # order is important and should be same as order of columns
    # displayed by datatables. For non sortable columns use empty
    # value like ''
    order_columns = [
        "eve_type_icon",
        "eve_type",
        "",
        "owner",
        "material_efficiency",
        "time_efficiency",
        "is_original",
        "runs",
        "pk",
        "location",
        "industryjob",
    ]

    # set max limit of records returned, this is used to protect our site if someone tries to attack our site
    # and make it return huge amount of data
    max_display_length = 500

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._user_has_location_permission = None

    def initialize(self, *args, **kwargs):
        super().initialize(*args, **kwargs)
        self._user_has_location_permission = self.request.user.has_perm(
            "blueprints.view_blueprint_locations"
        )

    def get_initial_queryset(self):
        """Return queryset used as base for further sorting/filtering

        these are simply objects displayed in datatable
        You should not filter data returned here by any filter values entered by user. This is because
        we need some base queryset to count total number of records.
        """
        return Blueprint.objects.user_has_access(
            self.request.user
        ).annotate_location_name()

    def filter_queryset(self, qs):
        def apply_search_filter(qs, column_num, field):
            my_filter = self.request.GET.get(
                f"columns[{column_num}][search][value]", None
            )
            if my_filter:
                if self.request.GET.get(f"columns[{column_num}][search][regex]", False):
                    kwargs = {f"{field}__iregex": my_filter}
                else:
                    kwargs = {f"{field}__istartswith": my_filter}
                return qs.filter(**kwargs)
            return qs

        qs = qs.annotate_is_bpo().annotate_owner_name()
        qs = apply_search_filter(qs, 9, "location_name")
        qs = apply_search_filter(qs, 3, "owner_name")
        qs = apply_search_filter(qs, 4, "material_efficiency")
        qs = apply_search_filter(qs, 5, "time_efficiency")
        qs = apply_search_filter(qs, 6, "is_bpo")

        search = self.request.GET.get("search[value]", None)
        if search:
            qs = qs.filter(eve_type__name__icontains=search)

        return qs

    # pylint: disable = too-many-return-statements
    def render_column(self, row, column):
        if column == "eve_type_icon":
            variant = EveType.IconVariant.BPC if row.runs else EveType.IconVariant.BPO
            return format_html(
                '<img src="{}" width="{}" height="{}">',
                row.eve_type.icon_url(size=64, variant=variant),
                BLUEPRINTS_LIST_ICON_OUTPUT_SIZE,
                BLUEPRINTS_LIST_ICON_OUTPUT_SIZE,
            )

        if column == "location":
            if self._user_has_location_permission:
                return row.location_name
            return gettext_lazy("(Unknown)")

        if column == "is_original":
            return "Yes" if row.is_original else "No"

        if column == "owner":
            if row.owner.corporation:
                return {
                    "display": (
                        "<span class='fas fa-briefcase'></span>&nbsp;"
                        + row.owner.corporation.corporation_name
                    ),
                    "sort": row.owner.corporation.corporation_name,
                }
            return {
                "display": (
                    "<span class='fas fa-user'></span>&nbsp;"
                    + row.owner.character.character.character_name
                ),
                "sort": row.owner.character.character.character_name,
            }

        return super().render_column(row, column)


# @login_required
# @permissions_required("blueprints.basic_access")
# def list_blueprints(request):
#     from . import convert_blueprint

#     blueprint_rows = [
#         convert_blueprint(blueprint, request.user) for blueprint in blueprints_query
#     ]

#     return JsonResponse(blueprint_rows, safe=False)
