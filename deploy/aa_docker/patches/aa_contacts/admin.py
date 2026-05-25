from django.apps import apps
from django.contrib import admin

from .models import (
    AllianceContact,
    AllianceToken,
    CorporationContact,
    CorporationToken,
    StandingFilter,
)


@admin.register(AllianceContact)
class AllianceContactAdmin(admin.ModelAdmin):
    exclude = ("contact_id",)
    readonly_fields = ("alliance", "contact_type", "standing", "labels")


@admin.register(CorporationContact)
class CorporationContactAdmin(admin.ModelAdmin):
    exclude = ("contact_id",)
    readonly_fields = ("corporation", "contact_type", "standing", "labels")


@admin.register(AllianceToken)
class AllianceTokenAdmin(admin.ModelAdmin):
    list_display = ("alliance", "token", "last_update")
    search_fields = ("alliance__alliance_name", "token__character_name")
    raw_id_fields = ("alliance", "token")


@admin.register(CorporationToken)
class CorporationTokenAdmin(admin.ModelAdmin):
    list_display = ("corporation", "token", "last_update")
    search_fields = ("corporation__corporation_name", "token__character_name")
    raw_id_fields = ("corporation", "token")


class StandingFilterAdmin(admin.ModelAdmin):
    raw_id_fields = ("corporations", "alliances")


if apps.is_installed("securegroups"):
    admin.site.register(StandingFilter, StandingFilterAdmin)
