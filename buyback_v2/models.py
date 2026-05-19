from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class VariantSelection(models.TextChoices):
    """How to pick between market (unrefined) and reprocess values per line."""

    LEGACY_MAX = "legacy_max", "Legacy — highest of raw / reprocess / compressed"
    PREFER_REPROCESS = (
        "prefer_reprocess",
        "Prefer reprocess — use market price only if it beats reprocess",
    )
    CORP_MIN = "corp_min", "Corp minimum — lower of reprocess vs market (exclude compressed)"
    REPROCESS_ONLY = "reprocess_only", "Reprocess / refined only"
    MARKET_ONLY = "market_only", "Market (unrefined) only"


class PriceBasis(models.TextChoices):
    PROGRAM = "program", "Use program price type (Buy / Sell / Split)"
    BUY = "buy", "Jita buy"
    SELL = "sell", "Jita sell"
    SPLIT = "split", "Split (median of buy and sell)"


class ProgramPricingProfile(models.Model):
    """Per-program buyback v2 pricing rules (aa-buybackprogram Program unchanged)."""

    program = models.OneToOneField(
        "buybackprogram.Program",
        on_delete=models.CASCADE,
        related_name="pricing_v2",
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Use v2 Janice line pricing for this program. Disable to fall back to stock buyback math.",
    )
    variant_selection = models.CharField(
        max_length=32,
        choices=VariantSelection.choices,
        default=VariantSelection.PREFER_REPROCESS,
    )
    price_basis = models.CharField(
        max_length=16,
        choices=PriceBasis.choices,
        default=PriceBasis.PROGRAM,
        help_text="Which Janice column to use before taxes. Program default uses each program's price type.",
    )
    jita_buy_percent = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Multiplier applied to the chosen line price (percent of Jita buy/split/sell basis).",
    )
    include_compressed = models.BooleanField(
        default=True,
        help_text="When comparing variants, still allow compressed ore value to win if higher.",
    )
    reprocess_non_ore = models.BooleanField(
        default=True,
        help_text="Compute reprocess value for any item with SDE materials, not only ore/ice groups.",
    )
    force_janice_prices = models.BooleanField(
        default=True,
        help_text="Fetch missing item prices from Janice instead of Fuzzwork when building a quote.",
    )
    public_calculator_enabled = models.BooleanField(
        default=False,
        help_text="Allow anonymous users to price items on the public calculator (no contract tracking).",
    )
    public_multiplier = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=Decimal("0.9000"),
        validators=[MinValueValidator(Decimal("0.0001")), MaxValueValidator(Decimal("2.0000"))],
        help_text="Default payout multiplier for public (no-login) quotes when no public tier is defined.",
    )

    class Meta:
        verbose_name = "Buyback v2 pricing profile"
        verbose_name_plural = "Buyback v2 pricing profiles"

    def __str__(self) -> str:
        return f"v2 pricing for program {self.program_id}"


class EntityType(models.TextChoices):
    CORPORATION = "corporation", "Corporation"
    ALLIANCE = "alliance", "Alliance"
    CHARACTER = "character", "Character"


class PricingTier(models.Model):
    """Named multiplier bucket (e.g. ally 95%, corp 90%)."""

    program_profile = models.ForeignKey(
        ProgramPricingProfile,
        on_delete=models.CASCADE,
        related_name="tiers",
    )
    name = models.CharField(max_length=64)
    multiplier = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=Decimal("1.0000"),
        validators=[MinValueValidator(Decimal("0.0001")), MaxValueValidator(Decimal("2.0000"))],
        help_text="Line prices and contract total are multiplied by this (0.9 = 90% of calculated value).",
    )
    priority = models.PositiveIntegerField(
        default=0,
        help_text="Higher priority tiers are evaluated first when multiple rules could match.",
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Applies to the no-login public calculator (highest priority public tier wins).",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Fallback tier for logged-in users with no corp/alliance rule match.",
    )

    class Meta:
        ordering = ["-priority", "name"]
        verbose_name = "Pricing tier"
        verbose_name_plural = "Pricing tiers"

    def __str__(self) -> str:
        return f"{self.name} ({self.multiplier})"


class PricingTierRule(models.Model):
    tier = models.ForeignKey(PricingTier, on_delete=models.CASCADE, related_name="rules")
    entity_type = models.CharField(max_length=16, choices=EntityType.choices)
    entity_id = models.BigIntegerField(help_text="EVE corporation ID, alliance ID, or character ID.")
    entity_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional label for admin (not used in matching).",
    )

    class Meta:
        verbose_name = "Pricing tier rule"
        verbose_name_plural = "Pricing tier rules"
        constraints = [
            models.UniqueConstraint(
                fields=["tier", "entity_type", "entity_id"],
                name="buyback_v2_unique_tier_rule",
            ),
        ]

    def __str__(self) -> str:
        label = self.entity_name or str(self.entity_id)
        return f"{self.get_entity_type_display()} {label}"
