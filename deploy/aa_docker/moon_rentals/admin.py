from django.contrib import admin

from .models import MoonPop, MoonPopMinerStatus


@admin.register(MoonPop)
class MoonPopAdmin(admin.ModelAdmin):
    list_display = (
        "location_label",
        "pop_at",
        "rental_kind",
        "private_owner",
        "system_name",
        "buyback_program_id",
    )
    list_filter = ("rental_kind", "system_name")
    search_fields = ("location_label", "system_name", "notes")
    raw_id_fields = ("private_owner",)


@admin.register(MoonPopMinerStatus)
class MoonPopMinerStatusAdmin(admin.ModelAdmin):
    list_display = (
        "moon_pop",
        "user",
        "buyback_status",
        "mined_quantity",
        "tracking_number",
        "has_compressed",
        "has_uncompressed",
    )
    list_filter = ("buyback_status",)
    raw_id_fields = ("moon_pop", "user")
