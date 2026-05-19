from eve_sde.models import (
    ItemGroup, ItemMarketGroup, ItemType, Region, SolarSystem,
)
from solo.admin import SingletonModelAdmin

from django.contrib import admin
from django.db.models import Q
from django.forms import ModelChoiceField, ModelMultipleChoiceField

from allianceauth.services.hooks import get_extension_logger
from esi.models import Token

from marketmanager.app_settings import (
    MARKETMANAGER_TASK_PRIORITY_MARGIN_CONFIGS,
    MARKETMANAGER_TASK_PRIORITY_PRICE_CONFIGS,
    MARKETMANAGER_TASK_PRIORITY_STRUCTURES,
    MARKETMANAGER_TASK_PRIORITY_SUPPLY_CONFIGS, discord_bot_active,
)
from marketmanager.models import (
    Channel, ManagedSupplyConfig, MarginConfig, Order, PriceConfig,
    PrivateConfig, PublicConfig, StatisticsConfig, Structure, SupplyConfig,
    Webhook,
)
from marketmanager.tasks import (
    fetch_markets_structures_structure_id, run_margin_config, run_price_config,
    run_supply_config,
)

from .admin_helpers import list_2_html_w_tooltips

logger = get_extension_logger(__name__)


@admin.register(PublicConfig)
class PublicConfigAdmin(SingletonModelAdmin):
    filter_horizontal = ["fetch_regions"]

    def formfield_for_manytomany(self, db_field, request, **kwargs) -> ModelMultipleChoiceField:
        if db_field.name == "fetch_regions":
            kwargs["queryset"] = Region.objects.filter(Q(id__lt=11000000) | Q(pk=19000001))
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(StatisticsConfig)
class StatisticsConfigAdmin(SingletonModelAdmin):
    filter_horizontal = ["calculate_regions"]

    def formfield_for_manytomany(self, db_field, request, **kwargs) -> ModelMultipleChoiceField:
        # This should filter regions to valid market regions, ie. no shattered, AT or Jove
        if db_field.name == "calculate_regions":
            kwargs["queryset"] = Region.objects.filter(Q(id__lt=11000000) | Q(pk=19000001))
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(PrivateConfig)
class PrivateConfigAdmin(admin.ModelAdmin):
    list_display = ['token', 'failed', 'failure_reason']
    filter_horizontal = ["valid_corporations", "valid_structures"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs) -> ModelChoiceField | None:
        if db_field.name == "token":
            required_scopes = ['esi-markets.structure_markets.v1']
            kwargs["queryset"] = Token.objects.all(
            ).require_scopes(required_scopes)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(SupplyConfig)
class SupplyConfigAdmin(admin.ModelAdmin):
    list_display = ['item_type', 'buy_order', 'volume', 'price', '_locations', 'last_result_volume', 'last_run']
    filter_horizontal = ["structure", "structure_type", "webhooks", "debug_webhooks", "solar_system", "region"]
    autocomplete_fields = ['item_type']
    list_filter = ['buy_order', 'webhooks', 'debug_webhooks', 'managed_supply_config']
    actions = ['run_selected_supply_configs']

    if discord_bot_active:
        filter_horizontal.append("channels")
        filter_horizontal.append("debug_channels")

    def formfield_for_manytomany(self, db_field, request, **kwargs) -> ModelMultipleChoiceField:
        # This should filter Citadels (1657) and NPC Stations (15) as viable Structure_Types for this selection
        # This should filter regions to valid market regions, ie. no shattered, AT or Jove
        if db_field.name == "structure_type":
            kwargs["queryset"] = ItemType.objects.filter(group__id__in=[15, 1404, 1406, 1657], published=1)
        if db_field.name == "region":
            kwargs["queryset"] = Region.objects.filter(Q(id__lt=11000000) | Q(pk=19000001))
        if db_field.name == "solar_system":
            kwargs["queryset"] = SolarSystem.objects.filter(id__lt="31000000")
        if db_field.name == "item_type":
            kwargs["queryset"] = ItemType.objects.filter(market_group__isnull=False, published=1)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @admin.action(description="Run Selected SupplyConfigs")
    def run_selected_supply_configs(modeladmin, request, queryset) -> None:
        for config in queryset:
            run_supply_config.apply_async(
                args=[config.id], priority=MARKETMANAGER_TASK_PRIORITY_SUPPLY_CONFIGS)

    def _locations(self, obj) -> str:
        locations = [x.name for x in obj.structure.order_by(
            'name')] + [x.name for x in obj.solar_system.order_by('name')] + [x.name for x in obj.region.order_by('name')]

        return list_2_html_w_tooltips(locations, 10)


@admin.register(PriceConfig)
class PriceConfigAdmin(admin.ModelAdmin):
    list_display = ['_types', 'buy_order', 'price', '_locations', 'last_run']
    filter_horizontal = [
        'item_type', "item_market_group", "item_group", "structure", "structure_type",
        "webhooks", "debug_webhooks", "solar_system", "region"]
    list_filter = ['buy_order', 'webhooks', 'debug_webhooks']
    actions = ['run_selected_price_configs']

    if discord_bot_active:
        filter_horizontal.append("channels")
        filter_horizontal.append("debug_channels")

    def formfield_for_foreignkey(self, db_field, request, **kwargs) -> ModelChoiceField | None:
        # Only items that have market groups?
        if db_field.name == "item_type":
            kwargs["queryset"] = ItemType.objects.filter(market_group__isnull=False, published=1)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs) -> ModelMultipleChoiceField:
        # This should filter Citadels (1657) and NPC Stations (15) as viable Structure_Types for this selection
        # This should filter regions to valid market regions, ie. no shattered, AT or Jove
        if db_field.name == "structure_type":
            kwargs["queryset"] = ItemType.objects.filter(group__id__in=[15, 1404, 1406, 1657], published=1)
        if db_field.name == "region":
            kwargs["queryset"] = Region.objects.filter(Q(id__lt=11000000) | Q(pk=19000001))
        if db_field.name == "solar_system":
            kwargs["queryset"] = SolarSystem.objects.filter(id__lt="31000000")
        if db_field.name == "item_type":
            kwargs["queryset"] = ItemType.objects.filter(market_group__isnull=False, published=1)
        if db_field.name == "item_group":
            kwargs["queryset"] = ItemGroup.objects.filter(published=1)
        if db_field.name == "item_market_group":
            kwargs["queryset"] = ItemMarketGroup.objects.filter(parent_group__isnull=True)

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @admin.action(description="Run Selected PriceConfig")
    def run_selected_price_configs(modeladmin, request, queryset) -> None:
        for config in queryset:
            run_price_config.apply_async(
                args=[config.id], priority=MARKETMANAGER_TASK_PRIORITY_PRICE_CONFIGS)  # pyright: ignore[reportCallIssue]

    def _locations(self, obj):
        my_groups = [x.name for x in obj.structure.order_by('name')]

        return list_2_html_w_tooltips(my_groups, 10)

    def _types(self, obj):
        my_groups = [x.name for x in obj.item_type.order_by('name')]

        return list_2_html_w_tooltips(my_groups, 10)


@admin.register(MarginConfig)
class MarginConfigAdmin(admin.ModelAdmin):
    list_display = ['_types', 'importing', 'source_buy', 'destination_buy', 'margin_percent' , 'freight_cost', 'last_run']
    filter_horizontal = [
        'item_type', "item_market_group", "item_group",
        "webhooks", "debug_webhooks",
        "source_structure", "source_station" , "source_solar_system", "source_region",
        "destination_structure", "destination_station", "destination_solar_system", "destination_region"]
    list_filter = ['importing','source_buy', 'destination_buy', 'webhooks', 'debug_webhooks']
    actions = ['run_selected_price_configs']

    if discord_bot_active:
        filter_horizontal.append("channels")
        filter_horizontal.append("debug_channels")

    def formfield_for_foreignkey(self, db_field, request, **kwargs) -> ModelChoiceField | None:
        # Only items that have market groups?
        if db_field.name == "item_type":
            kwargs["queryset"] = ItemType.objects.filter(
                market_group__isnull=False, published=1)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs) -> ModelMultipleChoiceField:
        # This should filter Citadels (1657) and NPC Stations (15) as viable Structure_Types for this selection
        # This should filter regions to valid market regions, ie. no shattered, AT or Jove
        if db_field.name == "structure_type":
            kwargs["queryset"] = ItemType.objects.filter(group__id__in=[15, 1404, 1406, 1657], published=1)
        if db_field.name == "source_region":
            kwargs["queryset"] = Region.objects.filter(Q(id__lt=11000000) | Q(pk=19000001))
        if db_field.name == "destination_region":
            kwargs["queryset"] = Region.objects.filter(Q(id__lt=11000000) | Q(pk=19000001))
        if db_field.name == "source_solar_system":
            kwargs["queryset"] = SolarSystem.objects.filter(id__lt="31000000")
        if db_field.name == "destination_solar_system":
            kwargs["queryset"] = SolarSystem.objects.filter(id__lt="31000000")
        if db_field.name == "item_type":
            kwargs["queryset"] = ItemType.objects.filter(market_group__isnull=False, published=1)
        if db_field.name == "item_group":
            kwargs["queryset"] = ItemGroup.objects.filter(published=1)
        if db_field.name == "item_market_group":
            kwargs["queryset"] = ItemMarketGroup.objects.filter(parent_group__isnull=True)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @admin.action(description="Run Selected MarginConfig")
    def run_selected_price_configs(modeladmin, request, queryset) -> None:
        for config in queryset:
            run_margin_config.apply_async(
                args=[config.id], priority=MARKETMANAGER_TASK_PRIORITY_MARGIN_CONFIGS)

    def _types(self, obj):
        my_groups = [x.name for x in obj.item_type.order_by('name')]

        return list_2_html_w_tooltips(my_groups, 10)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('item_type', 'price', 'solar_system', 'is_buy_order',
                    'issued_by_character', 'issued_by_corporation', 'updated_at')


@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    list_display = ('name', 'solar_system', 'item_type', 'owner_id', 'pull_market', 'updated_at')
    actions = ['pull_selected_structure_orders']
    autocomplete_fields = ['item_type']

    @admin.action(description="Pull order from Selected Structures")
    def pull_selected_structure_orders(modeladmin, request, queryset) -> None:
        for structure in queryset:
            fetch_markets_structures_structure_id.apply_async(
                args=[structure.structure_id], priority=MARKETMANAGER_TASK_PRIORITY_STRUCTURES)


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ('name', )


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ('name', )


@admin.register(ManagedSupplyConfig)
class ManagedSupplyConfigAdmin(admin.ModelAdmin):
    list_display = ['managed_app_reason', 'managed_quantity', 'managed_app_identifier']
    filter_horizontal = [
        "managed_structure", "managed_structure_type", "managed_webhooks",
        "managed_debug_webhooks", "managed_solar_system", "managed_region"]
    list_filter = ['managed_buy_order', 'managed_webhooks', 'managed_debug_webhooks']

    if discord_bot_active:
        filter_horizontal.append("managed_channels")
        filter_horizontal.append("managed_debug_channels")

    def formfield_for_foreignkey(self, db_field, request, **kwargs) -> ModelChoiceField | None:
        # Only items that have market groups?
        if db_field.name == "managed_item_type":
            kwargs["queryset"] = ItemType.objects.filter(
                market_group__isnull=False, published=1)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs) -> ModelMultipleChoiceField:
        # This should filter Citadels (1657) and NPC Stations (15) as viable Structure_Types for this selection
        # This should filter regions to valid market regions, ie. no shattered, AT or Jove
        if db_field.name == "managed_structure_type":
            kwargs["queryset"] = ItemType.objects.filter(group__id__in=[15, 1404, 1406, 1657], published=1)
        if db_field.name == "managed_region":
            kwargs["queryset"] = Region.objects.filter(Q(id__lt=11000000) | Q(pk=19000001))
        if db_field.name == "managed_solar_system":
            kwargs["queryset"] = SolarSystem.objects.filter(id__lt="31000000")
        return super().formfield_for_manytomany(db_field, request, **kwargs)
