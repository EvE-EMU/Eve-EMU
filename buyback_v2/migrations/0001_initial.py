import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("buybackprogram", "0017_alter_contract_price_alter_contract_volume_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProgramPricingProfile",
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
                ("enabled", models.BooleanField(default=True)),
                (
                    "variant_selection",
                    models.CharField(
                        choices=[
                            ("legacy_max", "Legacy — highest of raw / reprocess / compressed"),
                            (
                                "prefer_reprocess",
                                "Prefer reprocess — use market price only if it beats reprocess",
                            ),
                            (
                                "corp_min",
                                "Corp minimum — lower of reprocess vs market (exclude compressed)",
                            ),
                            ("reprocess_only", "Reprocess / refined only"),
                            ("market_only", "Market (unrefined) only"),
                        ],
                        default="prefer_reprocess",
                        max_length=32,
                    ),
                ),
                (
                    "price_basis",
                    models.CharField(
                        choices=[
                            ("program", "Use program price type (Buy / Sell / Split)"),
                            ("buy", "Jita buy"),
                            ("sell", "Jita sell"),
                            ("split", "Split (median of buy and sell)"),
                        ],
                        default="program",
                        max_length=16,
                    ),
                ),
                (
                    "jita_buy_percent",
                    models.PositiveSmallIntegerField(
                        default=100,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(100),
                        ],
                    ),
                ),
                ("include_compressed", models.BooleanField(default=True)),
                ("reprocess_non_ore", models.BooleanField(default=True)),
                ("force_janice_prices", models.BooleanField(default=True)),
                (
                    "program",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pricing_v2",
                        to="buybackprogram.program",
                    ),
                ),
            ],
            options={
                "verbose_name": "Buyback v2 pricing profile",
                "verbose_name_plural": "Buyback v2 pricing profiles",
            },
        ),
    ]
