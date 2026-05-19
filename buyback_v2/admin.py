from django.contrib import admin

from buyback_v2.models import PricingTier, PricingTierRule, ProgramPricingProfile


class PricingTierRuleInline(admin.TabularInline):
    model = PricingTierRule
    extra = 1
    fields = ("entity_type", "entity_id", "entity_name")


class PricingTierInline(admin.TabularInline):
    model = PricingTier
    extra = 1
    fields = ("name", "multiplier", "priority", "is_public", "is_default")
    show_change_link = True


@admin.register(PricingTier)
class PricingTierAdmin(admin.ModelAdmin):
    list_display = ("name", "program_profile", "multiplier", "priority", "is_public", "is_default")
    list_filter = ("is_public", "is_default", "program_profile")
    inlines = [PricingTierRuleInline]


@admin.register(ProgramPricingProfile)
class ProgramPricingProfileAdmin(admin.ModelAdmin):
    list_display = (
        "program",
        "enabled",
        "variant_selection",
        "jita_buy_percent",
        "public_calculator_enabled",
        "public_multiplier",
    )
    list_filter = ("enabled", "variant_selection", "public_calculator_enabled")
    search_fields = ("program__name", "program__owner__name")
    inlines = [PricingTierInline]
    fieldsets = (
        (None, {"fields": ("program", "enabled")}),
        (
            "Janice / Jita line pricing",
            {
                "fields": (
                    "price_basis",
                    "jita_buy_percent",
                    "variant_selection",
                    "include_compressed",
                    "reprocess_non_ore",
                    "force_janice_prices",
                ),
            },
        ),
        (
            "Public calculator (no login)",
            {
                "fields": ("public_calculator_enabled", "public_multiplier"),
            },
        ),
    )
