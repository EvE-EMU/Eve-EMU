from django.contrib import admin

from emu_moons.models import (
    DiscordDeliveryLog,
    DiscordWebhookConfig,
    EmuExtraction,
    EmuExtractionLedgerLine,
    EmuInvoice,
    EmuInvoiceLine,
    EmuMoonsSettings,
    MoonTypeTaxRate,
    OrePriceSnapshot,
    StructureTaxProfile,
)


@admin.register(EmuMoonsSettings)
class EmuMoonsSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not EmuMoonsSettings.objects.exists()


@admin.register(StructureTaxProfile)
class StructureTaxProfileAdmin(admin.ModelAdmin):
    list_display = (
        "structure_name",
        "system_name",
        "structure_class",
        "private_owner",
        "updated_at",
    )
    list_filter = ("structure_class",)
    search_fields = ("structure_name", "system_name", "private_owner__username")
    raw_id_fields = ("private_owner",)


@admin.register(MoonTypeTaxRate)
class MoonTypeTaxRateAdmin(admin.ModelAdmin):
    list_display = ("structure_class", "moon_rarity", "tax_rate_percent", "active")
    list_filter = ("structure_class", "active")


class EmuInvoiceLineInline(admin.TabularInline):
    model = EmuInvoiceLine
    extra = 0


@admin.register(EmuInvoice)
class EmuInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "character_name",
        "status",
        "original_tax_isk",
        "penalty_isk",
        "amount_paid_isk",
        "due_at",
    )
    list_filter = ("status",)
    search_fields = ("invoice_number", "character_name", "corporation_name")
    inlines = [EmuInvoiceLineInline]


class EmuExtractionLedgerLineInline(admin.TabularInline):
    model = EmuExtractionLedgerLine
    extra = 0
    readonly_fields = (
        "miner_character_name",
        "type_name",
        "quantity",
        "gross_isk",
    )


@admin.register(EmuExtraction)
class EmuExtractionAdmin(admin.ModelAdmin):
    list_display = (
        "extraction_number",
        "moon_label",
        "system_name",
        "structure_class",
        "popped_at",
        "invoices_generated",
    )
    list_filter = ("structure_class", "invoices_generated")
    inlines = [EmuExtractionLedgerLineInline]


@admin.register(OrePriceSnapshot)
class OrePriceSnapshotAdmin(admin.ModelAdmin):
    list_display = ("type_name", "refined_isk_per_unit", "snapshot_at", "source")
    list_filter = ("source",)


@admin.register(DiscordWebhookConfig)
class DiscordWebhookConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "enabled", "created_at")


@admin.register(DiscordDeliveryLog)
class DiscordDeliveryLogAdmin(admin.ModelAdmin):
    list_display = ("webhook", "notification_type", "response_code", "succeeded", "created_at")
    list_filter = ("succeeded", "failed_permanently")
