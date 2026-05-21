from django.contrib import admin, messages

from corp_orders.models import FreightOrder, FreightOrdersSettings
from corp_orders.services.lifecycle import cancel_order


@admin.register(FreightOrdersSettings)
class FreightOrdersSettingsAdmin(admin.ModelAdmin):
    list_display = ("origin_system", "destination_system", "freight_volume_threshold_m3")


@admin.register(FreightOrder)
class FreightOrderAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "character_name",
        "claimed_character_name",
        "speed",
        "contract_price_isk",
        "status",
        "created_at",
    )
    list_filter = ("status", "speed", "issuer_kind")
    search_fields = ("code", "character_name", "contract_description")
    readonly_fields = ("code", "created_at", "updated_at")
    actions = ("cancel_selected_orders",)

    @admin.action(description="Cancel selected orders (kill job)")
    def cancel_selected_orders(self, request, queryset):
        cancelled = 0
        skipped = 0
        for order in queryset:
            if cancel_order(order):
                cancelled += 1
            else:
                skipped += 1
        if cancelled:
            self.message_user(request, f"Cancelled {cancelled} order(s).", messages.SUCCESS)
        if skipped:
            self.message_user(
                request,
                f"Skipped {skipped} order(s) (already completed or cancelled).",
                messages.WARNING,
            )
