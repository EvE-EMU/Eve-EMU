from django.contrib import admin

from moon_tsar.models import (
    MoonExtractionEvent,
    MoonExtractionLedgerLine,
    MoonHeatmapCell,
    MoonOreTaxRate,
    MoonRentalProfile,
    MoonTaxBill,
    MoonTaxPayment,
    MoonTsarSettings,
)


@admin.register(MoonTsarSettings)
class MoonTsarSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not MoonTsarSettings.objects.exists()


@admin.register(MoonOreTaxRate)
class MoonOreTaxRateAdmin(admin.ModelAdmin):
    list_display = ("type_name", "type_id", "tax_rate_percent", "active")
    search_fields = ("type_name",)


@admin.register(MoonExtractionEvent)
class MoonExtractionEventAdmin(admin.ModelAdmin):
    list_display = ("moon_label", "popped_at", "tracking_ends_at", "total_tax_isk")
    search_fields = ("moon_label", "system_name")


@admin.register(MoonTaxBill)
class MoonTaxBillAdmin(admin.ModelAdmin):
    list_display = ("character_name", "extraction", "due_date", "status", "total_tax_isk")
    search_fields = ("character_name", "public_id")
    readonly_fields = ("public_id",)


admin.site.register(MoonExtractionLedgerLine)
admin.site.register(MoonTaxPayment)
admin.site.register(MoonRentalProfile)
admin.site.register(MoonHeatmapCell)
