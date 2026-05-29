from django.contrib import admin

from .models import MoonLease, MoonRentalApplication, RentalModuleSettings


@admin.register(RentalModuleSettings)
class RentalModuleSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "corporation_id",
        "wallet_division",
        "payment_keyword",
        "due_day_of_month",
        "updated_at",
    )


@admin.register(MoonLease)
class MoonLeaseAdmin(admin.ModelAdmin):
    list_display = (
        "location_label",
        "renter_corporation",
        "status",
        "payment_status",
        "monthly_rent_isk",
        "main_poc",
        "updated_at",
    )
    list_filter = ("status", "payment_status")
    search_fields = ("renter_corporation", "payment_reference")
    raw_id_fields = ("moon", "main_poc")


@admin.register(MoonRentalApplication)
class MoonRentalApplicationAdmin(admin.ModelAdmin):
    list_display = ("moon", "applicant", "renter_corporation", "status", "created_at")
    list_filter = ("status",)
