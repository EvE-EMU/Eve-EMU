from django.contrib import admin

from .models import BlueprintCopyListing, IndustrialProject, IndustrialSubOrder


class IndustrialSubOrderInline(admin.TabularInline):
    model = IndustrialSubOrder
    extra = 0


@admin.register(IndustrialProject)
class IndustrialProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "esi_corporation_id", "created_at")
    search_fields = ("name", "esi_external_ref")
    inlines = (IndustrialSubOrderInline,)


@admin.register(BlueprintCopyListing)
class BlueprintCopyListingAdmin(admin.ModelAdmin):
    list_display = ("type_id", "owner_label", "runs_remaining", "is_available")
    list_filter = ("is_available",)
