"""Admin site for Blueprints."""

# pylint: disable = missing-class-docstring, missing-function-docstring

from typing import Any

from django.contrib import admin
from django.db.models import QuerySet
from django.http.request import HttpRequest
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from . import tasks
from .models import Blueprint, IndustryJob, Location, Owner, Request


class LocationNameListFilter(admin.SimpleListFilter):
    title = _("location name")
    parameter_name = "location_name"

    def lookups(self, request, model_admin):
        qs = model_admin.get_queryset(request)
        return (
            (obj, obj)
            for obj in qs.values_list("location_name", flat=True)
            .distinct()
            .order_by("location_name")
        )

    def queryset(self, request, queryset):
        if value := self.value():
            return queryset.filter(location_name=value)
        return None


class BpoListFilter(admin.SimpleListFilter):
    title = _("is BPO")
    parameter_name = "is_bpo"

    def lookups(self, request, model_admin):
        return (
            ("yes", _("yes")),
            ("no", _("no")),
        )

    def queryset(self, request, queryset):
        if value := self.value():
            return queryset.filter(is_bpo=value)
        return None


class LocationFlagListFilter(admin.SimpleListFilter):
    title = _("location flag")
    parameter_name = "location_flag"

    def lookups(self, request, model_admin):
        qs = model_admin.get_queryset(request)
        return (
            (obj, Blueprint.LocationFlag(obj).label)
            for obj in qs.values_list("location_flag", flat=True)
            .distinct()
            .order_by("location_flag")
        )

    def queryset(self, request, queryset):
        if value := self.value():
            return queryset.filter(location_flag=value)
        return None


@admin.register(Blueprint)
class BlueprintAdmin(admin.ModelAdmin):
    list_display = (
        "_type",
        "_owner",
        "_location_name",
        "location_flag",
        "_material_efficiency",
        "_time_efficiency",
        "_original",
    )
    list_filter = [
        "owner",
        BpoListFilter,
        LocationNameListFilter,
        LocationFlagListFilter,
        ("eve_type__eve_group", admin.RelatedOnlyFieldListFilter),
    ]
    search_fields = ["eve_type__name"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        qs = (
            super()
            .get_queryset(request)
            .annotate_is_bpo()
            .select_related("eve_type", "owner", "owner__corporation")
        )
        return qs.annotate_location_name()

    @admin.display(ordering="eve_type__name")
    def _type(self, obj):
        return obj.eve_type.name if obj.eve_type else None

    @admin.display(ordering="owner__name")
    def _owner(self, obj):
        return obj.owner.name

    @admin.display(ordering="is_bpo", boolean=True, description="BPO")
    def _original(self, obj) -> bool:
        return obj.is_bpo == "yes"

    def _location_name(self, obj):
        return obj.location_name

    @admin.display(description="ME", ordering="material_efficiency")
    def _material_efficiency(self, obj):
        return obj.material_efficiency

    @admin.display(description="TE", ordering="time_efficiency")
    def _time_efficiency(self, obj):
        return obj.time_efficiency

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class LocationHasBlueprintsListFilter(admin.SimpleListFilter):
    title = _("has blueprints")
    parameter_name = "has_blueprints"

    def lookups(self, request, model_admin):
        return (("yes", _("yes")), ("no", _("no")))

    def queryset(self, request, queryset):
        value = self.value()
        if value == "yes":
            return queryset.annotate_blueprint_count().filter(blueprint_count__gt=0)
        if value == "no":
            return queryset.annotate_blueprint_count().filter(blueprint_count=0)
        return None


class LocationHasNameListFilter(admin.SimpleListFilter):
    title = _("has name")
    parameter_name = "has_name"

    def lookups(self, request, model_admin):
        return (("yes", _("yes")), ("no", _("no")))

    def queryset(self, request, queryset):
        value = self.value()
        if value == "yes":
            return queryset.exclude(name="")
        if value == "no":
            return queryset.filter(name="")
        return None


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "_type",
        "_group",
        "_solar_system",
        "_parent",
        "_blueprint_count",
        "updated_at",
    )
    list_filter = (
        # ("parent", admin.RelatedOnlyFieldListFilter),
        LocationHasBlueprintsListFilter,
        LocationHasNameListFilter,
        (
            "eve_solar_system__eve_constellation__eve_region",
            admin.RelatedOnlyFieldListFilter,
        ),
        ("eve_solar_system", admin.RelatedOnlyFieldListFilter),
        ("eve_type__eve_group", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = ["name"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        qs = super().get_queryset(request)
        return qs.select_related(
            "eve_solar_system",
            "eve_solar_system__eve_constellation__eve_region",
            "eve_type",
            "eve_type__eve_group",
            "parent",
            "parent__eve_type",
        ).annotate_blueprint_count()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(ordering="eve_solar_system__name")
    def _solar_system(self, obj: Location):
        return obj.eve_solar_system.name if obj.eve_solar_system else None

    @admin.display(ordering="eve_type__name")
    def _type(self, obj: Location):
        return obj.eve_type.name if obj.eve_type else None

    @admin.display(ordering="eve_type__eve_group__name")
    def _group(self, obj: Location):
        return obj.eve_type.eve_group.name if obj.eve_type else None

    def _parent(self, obj: Location):
        if not obj.parent:
            return None
        url = reverse("admin:blueprints_location_change", args=(obj.parent.id,))
        return format_html('<a href="{}">{}</a>', url, obj.parent)

    @admin.display(ordering="blueprint_count")
    def _blueprint_count(self, obj: Location):
        return obj.blueprint_count


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ("__str__", "is_active", "_type", "character", "_blueprint_count")
    actions = ["activate_owners", "deactivate_owners", "update_locations"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        qs = (
            super()
            .get_queryset(request)
            .select_related("character__character", "corporation", "character__user")
            .annotate_blueprint_count()
        )
        return qs

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(ordering="blueprint_count")
    def _blueprint_count(self, obj: Owner):
        return obj.blueprint_count

    def _type(self, obj):
        return "Corporate" if obj.corporation else "Personal"

    @admin.action(description="Update locations for selected owners")
    def update_locations(self, request, queryset):
        for owner in queryset:
            tasks.update_locations_for_owner.delay(owner_pk=owner.pk)
        count = queryset.count()
        self.message_user(request, f"Started updating locations for {count} owners.")

    @admin.action(description="Activate selected owners")
    def activate_owners(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected owners")
    def deactivate_owners(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ("_type", "_requestor", "_owner", "_fulfilled_by")

    list_select_related = (
        "blueprint__eve_type",
        "requesting_user__profile__main_character",
    )
    search_fields = ["blueprint__eve_type__name"]

    def _type(self, obj):
        return obj.blueprint.eve_type.name if obj.blueprint.eve_type else None

    def _requestor(self, obj):
        return obj.requesting_user.profile.main_character.character_name

    def _owner(self, obj):
        return obj.blueprint.owner.name

    def _fulfilled_by(self, obj):
        return (
            obj.fulfulling_user.profile.main_character.character_name
            if obj.fulfulling_user
            else None
        )

    def has_add_permission(self, request):
        return False


@admin.register(IndustryJob)
class IndustryJobAdmin(admin.ModelAdmin):
    list_display = ("_blueprint", "_installer", "_activity")

    list_select_related = ("blueprint__eve_type",)
    search_fields = ["blueprint__eve_type__name"]

    def _blueprint(self, obj):
        return obj.blueprint.eve_type.name if obj.blueprint.eve_type else None

    def _installer(self, obj):
        return obj.installer.character_name

    def _activity(self, obj):
        return obj.get_activity_display()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
