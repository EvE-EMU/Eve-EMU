import datetime
from decimal import Decimal

from discord import SyncWebhook
from eve_sde.models import (
    ItemGroup, ItemMarketGroup, ItemType, NPCStation, Region, SolarSystem,
)
from solo.models import SingletonModel

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from esi.models import Token


class General(models.Model):
    """Meta model for app permissions"""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("basic_market_browser", "Can access the Standard Market Browser"),
            ("basic_market_watches", "Can view all SupplyConfigs and their status"),
            ("order_highlight_user", "Market orders owned by the user's characters may be highlighted in the standard/basic Market Browser"),
            ("order_highlight_corporation", "Market orders owned by any corporation a user is a member of may be highlighted in the standard/basic Market Browser WARNING: This has no checks for Corporation Roles."),
            ("advanced_market_browser", "Can access the Advanced Market Browser"),
            ("can_add_token_character", "Can add a Character Token with required scopes"),
            ("can_add_token_corporation", "Can add a Corpration Token with required scopes"),
        )


class Order(models.Model):
    """An EVE Market Order"""
    order_id = models.PositiveBigIntegerField(
        _("Order ID"),
        help_text=_("Unique order ID"),
        primary_key=True)
    item_type = models.ForeignKey(
        ItemType,
        verbose_name=_("Type"),
        on_delete=models.CASCADE)
    duration = models.PositiveSmallIntegerField(
        _("Duration"),
        help_text=_("Number of days the order was valid for (starting from the issued date). An order expires at time issued + duration"))
    is_buy_order = models.BooleanField(
        _("Buy Order"),
        default=False,
        help_text=_("True if the order is a bid (buy) order"),
        db_index=True)
    issued = models.DateTimeField(
        _("Issued"),
        help_text=_("Date and time when this order was issued"),
        auto_now=False,
        auto_now_add=False)
    location_id = models.PositiveBigIntegerField(
        _("Location ID"),
        help_text=_("ID of the location where order was placed"))
    solar_system = models.ForeignKey(
        SolarSystem,
        verbose_name=_("System"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,)
    region = models.ForeignKey(
        Region,
        related_name="+",
        verbose_name=_("Region"),
        on_delete=models.CASCADE)
    min_volume = models.PositiveIntegerField(
        _("Minimum Volume"),
        null=True,
        blank=True,
        help_text=_("For buy orders, the minimum quantity that will be accepted in a matching sell order"))
    price = models.DecimalField(
        _("Price"),
        max_digits=15,
        decimal_places=2,
        help_text=_("Cost per unit for this order"))
    RANGE_CHOICES = [
        ('1', _('1')),
        ('2', _('2')),
        ('3', _('3')),
        ('4', _('4')),
        ('5', _('5')),
        ('10', _('10')),
        ('20', _('20')),
        ('30', _('30')),
        ('40', _('40')),
        ('region', _('Region')),
        ('solarsystem', _('Solar System')),
        ('station', _('Station'))]
    range = models.CharField(
        _("Order Range"),
        max_length=12,
        choices=RANGE_CHOICES,
        help_text=_("Valid order range, numbers are ranges in jumps"))
    volume_remain = models.PositiveIntegerField(
        _("Volume Remaining"),
        help_text=_("Quantity of items still required or offered"))
    is_corporation = models.BooleanField(
        _("Is Corporation"),
        default=False,
        help_text=_("Signifies whether the buy/sell order was placed on behalf of a corporation."))
    wallet_division = models.PositiveSmallIntegerField(
        _("Wallet Division"),
        null=True,
        blank=True,
        help_text=_("The corporation wallet division used for this order."))
    issued_by_character = models.ForeignKey(
        EveCharacter,
        verbose_name=_("Character"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True)
    issued_by_corporation = models.ForeignKey(
        EveCorporationInfo,
        verbose_name=_("Corporation"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,)
    STATE_CHOICES = [
        ('', ''),
        ('cancelled', _('Cancelled')),
        ('expired ', _('Expired'))]
    state = models.CharField(
        _("Order State"),
        max_length=10,
        choices=STATE_CHOICES,
        help_text=_("Current order state, Only valid for Authenticated order History. Will not update from Public Market Data."),
        null=True,
        blank=True,)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Meta definitions
        """
        default_permissions = ()

    @property
    def expiry(self) -> datetime.datetime:
        return self.issued + datetime.timedelta(days=self.duration)


class Structure(models.Model):
    """An EVE Online Upwell Structure"""
    structure_id = models.PositiveBigIntegerField(
        _("Structure ID"),
        primary_key=True)
    name = models.CharField(
        _("Name"),
        max_length=60)
    owner_id = models.IntegerField(_("Owner Corporation ID"))
    solar_system = models.ForeignKey(
        SolarSystem,
        verbose_name=_("Solar System"),
        on_delete=models.CASCADE,
        related_name="+")
    item_type = models.ForeignKey(
        ItemType,
        verbose_name=_("Type"),
        on_delete=models.CASCADE,
        related_name="+",
        limit_choices_to={
            "item_group__id__in": [15, 1657],
            "published": 1})
    pull_market = models.BooleanField(
        _("Pull Market Orders"),
        help_text=_("Useful to ignore specific structures for _reasons_"),
        default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class Webhook(models.Model):
    name = models.CharField(
        _("Name"),
        max_length=100)
    url = models.URLField(
        _("URL"),
        max_length=200)
    enabled = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name

    def send_embed(self, embed) -> None:
        webhook = SyncWebhook.from_url(self.url)
        webhook.send(embed=embed, username="Market Manager")


class Channel(models.Model):
    name = models.CharField(
        _("Name"),
        max_length=100)
    id = models.BigIntegerField(
        primary_key=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        """
        Meta definitions
        """
        verbose_name = _('Channel')
        verbose_name_plural = _('Channels')


class ManagedSupplyConfig(models.Model):
    managed_app = models.CharField(
        _("Managed By App"),
        max_length=50,
        default="",
        help_text=_("The App managing this SupplyConfig"),
        blank=True)
    managed_app_identifier = models.CharField(
        _("Managed App-Identifier"),
        max_length=50,
        default="",
        help_text=_("An identifier relevant to the App managing this SupplyConfig"),
        blank=True)
    managed_app_reason = models.CharField(
        _("Managed App Reason"),
        max_length=50,
        default="",
        help_text=_("User Facing reason for this Managed SupplyConfig"),
        blank=True)
    managed_quantity = models.IntegerField(
        _("quantity"),
        help_text=_("Apply a multiplier to the volumes that will be generated"),
        default=1,
        blank=False)
    # Duped from Supplyonfig
    managed_buy_order = models.BooleanField(_("Buy Order"))
    # Location Rules, Combined
    managed_structure = models.ManyToManyField(
        Structure,
        verbose_name=_("Structure"),
        blank=True)
    managed_solar_system = models.ManyToManyField(
        SolarSystem,
        verbose_name=_("Solar System"),
        blank=True)
    managed_region = models.ManyToManyField(
        Region,
        related_name="+",
        verbose_name=_("Region"),
        blank=True)
    # Filter
    managed_structure_type = models.ManyToManyField(
        ItemType,
        help_text=_("Filter by structure Type/Size/Docking (ie, forts/keeps for cap fuel)"),
        verbose_name=_("Structure Type Filter"),
        blank=True)
    # Settings
    managed_jita_compare_percent = models.DecimalField(
        _("Jita Comparison %"),
        help_text=_("If set ignores Flat price value"),
        max_digits=4,
        decimal_places=0,
        default=Decimal(0),
        validators=[MinValueValidator(0), MaxValueValidator(1000)])
    # Destinations
    managed_webhooks = models.ManyToManyField(
        Webhook,
        verbose_name=_("Webhooks"),
        blank=True)
    managed_channels = models.ManyToManyField(
        Channel,
        verbose_name=_("Channels"),
        blank=True)
    managed_debug_webhooks = models.ManyToManyField(
        Webhook,
        verbose_name=_("Debug Webhook"),
        related_name="+",
        blank=True,
        help_text=_("Primarily for Testing/Debugging Purposes. This webhook will receive updates on Supplyonfigs that _dont_ notify. Because their Configs didnt Meet/Breach."))
    managed_debug_channels = models.ManyToManyField(
        Channel,
        verbose_name=_("Debug Channels"),
        related_name="+",
        blank=True,
        help_text=_("Primarily for Testing/Debugging Purposes. This webhook will receive updates on SupplyConfigs that _dont_ notify. Because their Configs didnt Meet/Breach."))

    def __str__(self) -> str:
        return self.managed_app_reason

    class Meta:
        """
        Meta definitions
        """
        verbose_name = _("Managed Supply Config")
        verbose_name_plural = _("Managed Supply Configs")


class SupplyConfig(models.Model):
    """
    Supply Alerts, Ensure adequate volume is on the market at a given price.
    """
    buy_order = models.BooleanField(_("Buy Order"))
    item_type = models.ForeignKey(
        ItemType,
        verbose_name=_("EVE Type"),
        on_delete=models.CASCADE,
        limit_choices_to={
            "item_group__isnull": False,
            "published": 1})
    # Location Rules, Combined
    structure = models.ManyToManyField(
        Structure,
        verbose_name=_("Structure"),
        blank=True)
    solar_system = models.ManyToManyField(
        SolarSystem,
        verbose_name=_("Solar System"),
        blank=True)
    region = models.ManyToManyField(
        Region,
        related_name="+",
        verbose_name=_("Region"),
        blank=True)
    # Filter
    structure_type = models.ManyToManyField(
        ItemType,
        related_name="+",
        help_text=_("Filter by structure Type/Size/Docking (ie, forts/keeps for cap fuel)"),
        verbose_name=_("Structure Type Filter"),
        blank=True)
    # Settings
    volume = models.IntegerField(
        _("Volume"),
        help_text=_("Set to Zero to check ANY/EVERY order against Price"),
        default=1,
        blank=False)
    price = models.DecimalField(
        _("Price"),
        help_text=_("Set to Zero to skip this filter"),
        default=Decimal(0),
        max_digits=15,
        decimal_places=2,
        blank=False)
    jita_compare_percent = models.DecimalField(
        _("Jita Comparison %"),
        help_text=_("If set ignores Flat price value"),
        max_digits=4,
        decimal_places=0,
        default=Decimal(0),
        validators=[MinValueValidator(0), MaxValueValidator(1000)])
    # Destinations
    webhooks = models.ManyToManyField(
        Webhook,
        verbose_name=_("Webhooks"),
        blank=True)
    channels = models.ManyToManyField(
        Channel,
        verbose_name=_("Channels"),
        blank=True)
    debug_webhooks = models.ManyToManyField(
        Webhook,
        verbose_name=_("Debug Webhook"),
        related_name="+",
        blank=True,
        help_text=_("Primarily for Testing/Debugging Purposes. This webhook will receive updates on SupplyConfigs that _dont_ notify. Because their Configs didnt Meet/Breach."))
    debug_channels = models.ManyToManyField(
        Channel,
        verbose_name=_("Debug Channels"),
        related_name="+",
        blank=True,
        help_text=_("Primarily for Testing/Debugging Purposes. This webhook will receive updates on SupplyConfigs that _dont_ notify. Because their Configs didnt Meet/Breach."))
    managed_supply_config = models.ForeignKey(
        ManagedSupplyConfig,
        verbose_name=_("Managed Watch Configs"),
        on_delete=models.CASCADE,
        blank=True,
        null=True)
    # Cached results from the last time this task was run
    last_run = models.DateTimeField(
        _("Last Task Runtime"),
        blank=True,
        null=True)
    last_result_volume = models.IntegerField(
        _("Last Result Volume"),
        help_text=_("The Volume returned the last time this WatchConfig was run"),
        blank=True,
        null=True)

    class Meta:
        """
        Meta definitions
        """
        verbose_name = _("Supply Config")
        verbose_name_plural = _("Supply Configs")


class PriceConfig(models.Model):
    """
    Price Alerts (scalp=True), Highlights orders that breach a given threshold to find Scalpers and market abuse.
    Price Alerts (Bargains=True), Flip the logic to find bargains like dreads in surrounding regions.
    """
    buy_order = models.BooleanField(
        _("Buy Order"),
        default=False)
    scalp = models.BooleanField(
        _("Scalp Finder?"),
        help_text=_("True for Scalp, False for Bargain"),
        default=False)
    item_type = models.ManyToManyField(
        ItemType,
        verbose_name=_("EVE Type"),
        blank=True)
    item_group = models.ManyToManyField(
        ItemGroup,
        verbose_name=_("EVE Inventory Group"),
        blank=True)
    item_market_group = models.ManyToManyField(
        ItemMarketGroup,
        verbose_name=_("EVE Market Group"),
        blank=True)
    minimum = models.DecimalField(
        _("Minimum Price"),
        help_text=("Minimum isk to consider an order at, Default: 1M"),
        default=Decimal(1000000),
        max_digits=15,
        decimal_places=2,
        blank=False)
    # Location Rules, Combined
    structure = models.ManyToManyField(
        Structure,
        verbose_name=_("Structure"),
        blank=True)
    solar_system = models.ManyToManyField(
        SolarSystem,
        verbose_name=_("Solar System"),
        blank=True)
    region = models.ManyToManyField(
        Region,
        related_name="+",
        verbose_name=_("Region"),
        blank=True)
    # Filter
    structure_type = models.ManyToManyField(
        ItemType,
        related_name="+",
        help_text=_("Filter by structure Type/Size/Docking (ie, forts/keeps for cap fuel)"),
        verbose_name=_("Structure Type Filter"),
        blank=True)
    # Settings
    jita_compare_percent = models.DecimalField(
        _("Jita Comparison %"),
        help_text=_("If set ignores Flat price value"),
        max_digits=4,
        decimal_places=0,
        default=Decimal(0),
        validators=[MinValueValidator(0), MaxValueValidator(1000)])
    price = models.DecimalField(
        _("Price"),
        help_text=_(
            "WARNING: Use Jita% when possible, this sets a flat price for ALL items included in this Config. Possibly useful for Caps/Soups"),
        default=Decimal(0),
        max_digits=15,
        decimal_places=2,
        blank=False)
    # Destinations
    webhooks = models.ManyToManyField(
        Webhook,
        verbose_name=_("Webhooks"),
        blank=True)
    channels = models.ManyToManyField(
        Channel,
        verbose_name=_("Channels"),
        blank=True)
    debug_webhooks = models.ManyToManyField(
        Webhook,
        verbose_name=_("Debug Webhook"),
        related_name="+",
        blank=True,
        help_text=_("Primarily for Testing/Debugging Purposes. This webhook will receive updates on PriceConfigs that _dont_ notify. Because their Configs didnt Meet/Breach."))
    debug_channels = models.ManyToManyField(
        Channel,
        verbose_name=_("Debug Channels"),
        related_name="+",
        blank=True,
        help_text=_("Primarily for Testing/Debugging Purposes. This webhook will receive updates on PriceConfigs that _dont_ notify. Because their Configs didnt Meet/Breach."))
    # Cached results from the last time this task was run
    last_run = models.DateTimeField(
        _("Last Task Runtime"),
        blank=True,
        null=True)

    class Meta:
        """
        Meta definitions
        """
        verbose_name = _("Price Config")
        verbose_name_plural = _("Price Configs")


class MarginConfig(models.Model):
    """
    Find high-margin opportunities in a destination system
    importing=True, source_buy=False, destination_buy=False. Buy in Jita, list on market for sale
    importing=True, source_buy=False, destination_buy=True. Buy in Jita, Dump to buy orders.
    """
    importing = models.BooleanField(
        _("Import Items?"),
        help_text=_("True for Importing, False for Exporting"),
        default=True)
    source_buy = models.BooleanField(
        _("Source Buy Orders?"),
        help_text=_("Buy orders in the Source?, False for Sell"),
        default=False)
    destination_buy = models.BooleanField(
        _("Destination Buy Orders?"),
        help_text=_("Buy orders in the Destination?, False for Sell"),
        default=False)
    margin_percent = models.DecimalField(
        _("% Margin"),
        help_text=_("% difference of an order to highlight"),
        max_digits=4,
        decimal_places=0,
        default=Decimal(5),
        validators=[MinValueValidator(0), MaxValueValidator(100)])
    freight_cost = models.IntegerField(
        _("Import Cost (ISK/m3)"),
        help_text=_("isk/m3 to optionally add to imported item prices"),
        default=0)

    # volume_percent = models.DecimalField(
    #     _("% Volume"),
    #     help_text=_("% of the market to use for compare, Zero to compare single volume"),
    #     max_digits=4,
    #     decimal_places=0,
    #     default=Decimal(5),
    #     validators=[MinValueValidator(0), MaxValueValidator(100)])
    # Items
    item_type = models.ManyToManyField(
        ItemType,
        related_name="+",
        verbose_name=_("EVE Type"),
        blank=True)
    item_group = models.ManyToManyField(
        ItemGroup,
        related_name="+",
        verbose_name=_("EVE Inventory Group"),
        blank=True)
    item_market_group = models.ManyToManyField(
        ItemMarketGroup,
        related_name="+",
        verbose_name=_("EVE Market Group"),
        blank=True)
    # Source Location Rules
    source_structure = models.ManyToManyField(
        Structure,
        related_name="+",
        verbose_name=_("Source Structure"),
        blank=True)
    source_station = models.ManyToManyField(
        NPCStation,
        related_name="+",
        verbose_name=_("Source Station"),
        blank=True)
    source_solar_system = models.ManyToManyField(
        SolarSystem,
        related_name="+",
        verbose_name=_("Source Solar System"),
        blank=True)
    source_region = models.ManyToManyField(
        Region,
        related_name="+",
        verbose_name=_("Source Region"),
        blank=True)
    # Destination Location Rules
    destination_structure = models.ManyToManyField(
        Structure,
        related_name="+",
        verbose_name=_("Destination Structure"),
        blank=True)
    destination_station = models.ManyToManyField(
        NPCStation,
        related_name="+",
        verbose_name=_("Destination Station"),
        blank=True)
    destination_solar_system = models.ManyToManyField(
        SolarSystem,
        related_name="+",
        verbose_name=_("Destination Solar System"),
        blank=True)
    destination_region = models.ManyToManyField(
        Region,
        related_name="+",
        verbose_name=_("Destination Region"),
        blank=True)
    # Destinations
    webhooks = models.ManyToManyField(
        Webhook,
        related_name="+",
        verbose_name=_("Webhooks"),
        blank=True)
    channels = models.ManyToManyField(
        Channel,
        related_name="+",
        verbose_name=_("Channels"),
        blank=True)
    debug_webhooks = models.ManyToManyField(
        Webhook,
        verbose_name=_("Debug Webhook"),
        related_name="+",
        blank=True,
        help_text=_("Primarily for Testing/Debugging Purposes. This webhook will receive updates on MarginConfigs that _dont_ notify. Because their Configs didnt Meet/Breach."))
    debug_channels = models.ManyToManyField(
        Channel,
        verbose_name=_("Debug Channels"),
        related_name="+",
        blank=True,
        help_text=_("Primarily for Testing/Debugging Purposes. This webhook will receive updates on MarginConfigs that _dont_ notify. Because their Configs didnt Meet/Breach."))
    # Cached results from the last time this task was run
    last_run = models.DateTimeField(
        _("Last Task Runtime"),
        blank=True,
        null=True)

    class Meta:
        """
        Meta definitions
        """
        verbose_name = _("Margin Configs")
        verbose_name_plural = _("Margin Configs")


class PublicConfig(SingletonModel):
    fetch_regions = models.ManyToManyField(
        Region,
        related_name="+",
        verbose_name=_("Fetch Regions"),
    )

    def __str__(self) -> str:
        return "Public Market Configuration"

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        """
        Meta definitions
        """
        verbose_name = _("Public Market Configuration")


class StatisticsConfig(SingletonModel):
    calculate_regions = models.ManyToManyField(
        Region,
        verbose_name=_("TypeStatistics Calculation Regions"),
    )

    def __str__(self) -> str:
        return "TypeStatistics Calculation Configuration"

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        """
        Meta definitions
        """
        verbose_name = _("TypeStatistics Calculation Configuration")


class PrivateConfig(models.Model):
    token = models.OneToOneField(
        Token,
        verbose_name=_("ESI Token"),
        on_delete=models.CASCADE,
    )
    valid_corporations = models.ManyToManyField(
        EveCorporationInfo,
        verbose_name=_("Valid Corporation Markets for this Token"),
        blank=True,
    )
    valid_structures = models.ManyToManyField(
        Structure,
        verbose_name=_("Valid Structure Markets for this Token"),
        blank=True,
    )
    failed = models.BooleanField(
        _("Disabled due to Failure, Check reason, adjust config and re-enable"))
    failure_reason = models.CharField(
        _("Failure Reason"),
        max_length=100,
        blank=True,
        default="Failure Reason")

    class Meta:
        """
        Meta definitions
        """
        verbose_name = _("Private Market Configuration")
        verbose_name_plural = _("Private Market Configurations")


class TypeStatistics(models.Model):
    item_type = models.ForeignKey(
        ItemType,
        verbose_name=_("Type"),
        on_delete=models.CASCADE
    )
    region = models.ForeignKey(
        Region,
        related_name="+",
        verbose_name=_("Region"),
        on_delete=models.CASCADE,
        blank=True,
        null=True
    )
    buy_fifth_percentile = models.DecimalField(
        _("Buy 5th Percentile"),
        max_digits=15,
        decimal_places=2
    )
    sell_fifth_percentile = models.DecimalField(
        _("Sell 5th Percentile"),
        max_digits=15,
        decimal_places=2
    )
    buy_weighted_average = models.DecimalField(
        _("Buy Weighted Average"),
        max_digits=15,
        decimal_places=2
    )
    sell_weighted_average = models.DecimalField(
        _("Sell Weighted Average"),
        max_digits=15,
        decimal_places=2
    )
    buy_median = models.DecimalField(
        _("Buy Median"),
        max_digits=15,
        decimal_places=2
    )
    sell_median = models.DecimalField(
        _("Sell Median"),
        max_digits=15,
        decimal_places=2
    )

    class Meta:
        """
        Meta definitions
        """
        default_permissions = ()
        verbose_name = _("Item Type Statistics")
        verbose_name_plural = _("Item Types Statistics")
