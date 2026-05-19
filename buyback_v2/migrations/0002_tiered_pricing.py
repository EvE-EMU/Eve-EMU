import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("buyback_v2", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="programpricingprofile",
            name="public_calculator_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Allow anonymous users to price items on the public calculator (no contract tracking).",
            ),
        ),
        migrations.AddField(
            model_name="programpricingprofile",
            name="public_multiplier",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0.9000"),
                help_text="Default payout multiplier for public (no-login) quotes when no public tier is defined.",
                max_digits=6,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.0001")),
                    django.core.validators.MaxValueValidator(Decimal("2.0000")),
                ],
            ),
        ),
        migrations.CreateModel(
            name="PricingTier",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=64)),
                (
                    "multiplier",
                    models.DecimalField(
                        decimal_places=4,
                        default=Decimal("1.0000"),
                        help_text="Line prices and contract total are multiplied by this (0.9 = 90% of calculated value).",
                        max_digits=6,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0.0001")),
                            django.core.validators.MaxValueValidator(Decimal("2.0000")),
                        ],
                    ),
                ),
                (
                    "priority",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Higher priority tiers are evaluated first when multiple rules could match.",
                    ),
                ),
                (
                    "is_public",
                    models.BooleanField(
                        default=False,
                        help_text="Applies to the no-login public calculator (highest priority public tier wins).",
                    ),
                ),
                (
                    "is_default",
                    models.BooleanField(
                        default=False,
                        help_text="Fallback tier for logged-in users with no corp/alliance rule match.",
                    ),
                ),
                (
                    "program_profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tiers",
                        to="buyback_v2.programpricingprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "Pricing tier",
                "verbose_name_plural": "Pricing tiers",
                "ordering": ["-priority", "name"],
            },
        ),
        migrations.CreateModel(
            name="PricingTierRule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "entity_type",
                    models.CharField(
                        choices=[
                            ("corporation", "Corporation"),
                            ("alliance", "Alliance"),
                            ("character", "Character"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "entity_id",
                    models.BigIntegerField(
                        help_text="EVE corporation ID, alliance ID, or character ID."
                    ),
                ),
                (
                    "entity_name",
                    models.CharField(
                        blank=True,
                        help_text="Optional label for admin (not used in matching).",
                        max_length=255,
                    ),
                ),
                (
                    "tier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rules",
                        to="buyback_v2.pricingtier",
                    ),
                ),
            ],
            options={
                "verbose_name": "Pricing tier rule",
                "verbose_name_plural": "Pricing tier rules",
            },
        ),
        migrations.AddConstraint(
            model_name="pricingtierrule",
            constraint=models.UniqueConstraint(
                fields=("tier", "entity_type", "entity_id"),
                name="buyback_v2_unique_tier_rule",
            ),
        ),
    ]
