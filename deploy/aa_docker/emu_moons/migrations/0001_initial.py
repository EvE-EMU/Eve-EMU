# Generated manually for EMU Moons initial schema

from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EmuMoonsPermissions",
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
            ],
            options={
                "managed": True,
                "default_permissions": (),
                "permissions": (
                    ("emu_moons_view_self", "EMU Moons — view own invoices"),
                    ("emu_moons_view_corp", "EMU Moons — view corporation invoices"),
                    (
                        "emu_moons_view_alliance",
                        "EMU Moons — alliance reporting and naughty list",
                    ),
                    (
                        "emu_moons_admin",
                        "EMU Moons — configure rates, structures, webhooks",
                    ),
                ),
            },
        ),
        migrations.CreateModel(
            name="EmuMoonsSettings",
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
                    "tax_corp_name",
                    models.CharField(default="Guns-R-Us Toy Company", max_length=128),
                ),
                ("corporation_id", models.BigIntegerField(default=98799892)),
                ("wallet_division", models.PositiveSmallIntegerField(default=1)),
                ("esi_token_id", models.PositiveIntegerField(blank=True, null=True)),
                ("ledger_match_hours", models.PositiveSmallIntegerField(default=48)),
                ("invoice_run_weekday", models.PositiveSmallIntegerField(default=3)),
                ("invoice_run_hour_utc", models.PositiveSmallIntegerField(default=12)),
                (
                    "mail_sender_name",
                    models.CharField(default="El Emu Moon Tzar", max_length=64),
                ),
                (
                    "mail_sender_character_id",
                    models.BigIntegerField(blank=True, null=True),
                ),
                (
                    "reprocess_yield",
                    models.DecimalField(
                        decimal_places=4, default=Decimal("0.8500"), max_digits=5
                    ),
                ),
                ("nationalized_extract_dow", models.PositiveSmallIntegerField(default=4)),
                (
                    "nationalized_extract_hour",
                    models.PositiveSmallIntegerField(default=18),
                ),
                ("corp_liability_days", models.PositiveSmallIntegerField(default=60)),
                (
                    "penalty_rate_per_week",
                    models.DecimalField(
                        decimal_places=4, default=Decimal("1.0000"), max_digits=6
                    ),
                ),
                ("grace_days_before_penalty", models.PositiveSmallIntegerField(default=30)),
                ("reminder_days_json", models.JSONField(blank=True, default=list)),
                ("alliance_logo_url", models.URLField(blank=True, max_length=512)),
                ("tax_portal_url", models.URLField(blank=True, max_length=512)),
                ("how_to_mine_url", models.URLField(blank=True, max_length=512)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "EMU Moons settings"},
        ),
        migrations.CreateModel(
            name="StructureTaxProfile",
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
                    "moonmining_refinery_id",
                    models.PositiveIntegerField(blank=True, null=True, unique=True),
                ),
                ("structure_name", models.CharField(max_length=255)),
                ("system_name", models.CharField(blank=True, max_length=128)),
                (
                    "structure_class",
                    models.CharField(
                        choices=[
                            ("public", "Public"),
                            ("nationalized", "Nationalized"),
                            ("private", "Private"),
                        ],
                        default="public",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["structure_name"]},
        ),
        migrations.CreateModel(
            name="MoonTypeTaxRate",
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
                    "structure_class",
                    models.CharField(
                        choices=[
                            ("public", "Public"),
                            ("nationalized", "Nationalized"),
                            ("private", "Private"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "moon_rarity",
                    models.CharField(
                        choices=[
                            ("r4", "R4"),
                            ("r8", "R8"),
                            ("r16", "R16"),
                            ("r32", "R32"),
                            ("r64", "R64"),
                            ("unknown", "Unknown"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "tax_rate_percent",
                    models.DecimalField(decimal_places=2, default=0, max_digits=6),
                ),
                ("active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["structure_class", "moon_rarity"],
                "unique_together": {("structure_class", "moon_rarity")},
            },
        ),
        migrations.CreateModel(
            name="OrePriceSnapshot",
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
                ("type_id", models.PositiveIntegerField()),
                ("type_name", models.CharField(blank=True, max_length=128)),
                (
                    "raw_isk_per_unit",
                    models.DecimalField(decimal_places=4, default=0, max_digits=20),
                ),
                (
                    "refined_isk_per_unit",
                    models.DecimalField(decimal_places=4, default=0, max_digits=20),
                ),
                ("jita_buy_json", models.JSONField(blank=True, default=dict)),
                ("snapshot_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("source", models.CharField(default="janice", max_length=32)),
            ],
            options={"ordering": ["-snapshot_at", "type_name"]},
        ),
        migrations.CreateModel(
            name="EmuExtraction",
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
                ("moonmining_extraction_id", models.PositiveIntegerField(unique=True)),
                ("extraction_number", models.PositiveIntegerField(db_index=True)),
                ("moon_label", models.CharField(max_length=255)),
                ("system_name", models.CharField(blank=True, max_length=128)),
                ("moon_number", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("region_name", models.CharField(blank=True, max_length=128)),
                ("structure_name", models.CharField(blank=True, max_length=255)),
                (
                    "structure_class",
                    models.CharField(
                        choices=[
                            ("public", "Public"),
                            ("nationalized", "Nationalized"),
                            ("private", "Private"),
                        ],
                        default="public",
                        max_length=16,
                    ),
                ),
                ("popped_at", models.DateTimeField()),
                ("ledger_window_end", models.DateTimeField()),
                ("invoices_generated", models.BooleanField(default=False)),
                ("invoices_generated_at", models.DateTimeField(blank=True, null=True)),
                ("discord_complete_sent", models.BooleanField(default=False)),
                (
                    "estimated_ore_value_isk",
                    models.DecimalField(decimal_places=2, default=0, max_digits=20),
                ),
                (
                    "estimated_tax_isk",
                    models.DecimalField(decimal_places=2, default=0, max_digits=20),
                ),
                ("ore_composition_json", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "structure_profile",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="extractions",
                        to="emu_moons.structuretaxprofile",
                    ),
                ),
            ],
            options={"ordering": ["-popped_at"]},
        ),
        migrations.CreateModel(
            name="DiscordWebhookConfig",
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
                ("webhook_url", models.URLField(max_length=512)),
                ("enabled", models.BooleanField(default=True)),
                ("notification_types", models.JSONField(blank=True, default=list)),
                ("mention_everyone", models.BooleanField(default=False)),
                ("mention_here", models.BooleanField(default=False)),
                ("mention_role_ids_json", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="EmuInvoice",
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
                ("invoice_number", models.CharField(db_index=True, max_length=16, unique=True)),
                ("character_id", models.BigIntegerField()),
                ("character_name", models.CharField(blank=True, max_length=128)),
                ("corporation_id", models.BigIntegerField(blank=True, null=True)),
                ("corporation_name", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("partial", "Partially paid"),
                            ("paid", "Paid"),
                            ("corp_liable", "Corporation liable"),
                            ("void", "Void"),
                        ],
                        default="open",
                        max_length=16,
                    ),
                ),
                ("issued_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("due_at", models.DateField()),
                (
                    "original_tax_isk",
                    models.DecimalField(decimal_places=2, default=0, max_digits=20),
                ),
                (
                    "penalty_isk",
                    models.DecimalField(decimal_places=2, default=0, max_digits=20),
                ),
                (
                    "amount_paid_isk",
                    models.DecimalField(decimal_places=2, default=0, max_digits=20),
                ),
                (
                    "total_volume_m3",
                    models.DecimalField(decimal_places=4, default=0, max_digits=20),
                ),
                ("mail_sent_at", models.DateTimeField(blank=True, null=True)),
                ("mail_error", models.TextField(blank=True)),
                ("corp_liability_at", models.DateTimeField(blank=True, null=True)),
                ("reminders_sent_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("wallet_transaction_id", models.BigIntegerField(blank=True, null=True)),
                ("wallet_division", models.PositiveSmallIntegerField(blank=True, null=True)),
                (
                    "extraction",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invoices",
                        to="emu_moons.emuextraction",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="emu_moon_invoices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-issued_at"],
                "unique_together": {("extraction", "user")},
            },
        ),
        migrations.CreateModel(
            name="EmuExtractionLedgerLine",
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
                ("miner_character_id", models.BigIntegerField()),
                ("miner_character_name", models.CharField(blank=True, max_length=128)),
                ("type_id", models.PositiveIntegerField()),
                ("type_name", models.CharField(blank=True, max_length=128)),
                ("quantity", models.BigIntegerField(default=0)),
                (
                    "volume_m3",
                    models.DecimalField(decimal_places=4, default=0, max_digits=20),
                ),
                (
                    "gross_isk",
                    models.DecimalField(decimal_places=2, default=0, max_digits=20),
                ),
                ("observer_log_id", models.PositiveIntegerField(blank=True, null=True)),
                ("mined_at", models.DateField(blank=True, null=True)),
                (
                    "extraction",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ledger_lines",
                        to="emu_moons.emuextraction",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["miner_character_name", "type_name"]},
        ),
        migrations.CreateModel(
            name="DiscordDeliveryLog",
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
                ("notification_type", models.CharField(max_length=64)),
                ("payload_json", models.JSONField(default=dict)),
                ("response_code", models.PositiveIntegerField(blank=True, null=True)),
                ("response_body", models.TextField(blank=True)),
                ("retry_count", models.PositiveSmallIntegerField(default=0)),
                ("succeeded", models.BooleanField(default=False)),
                ("failed_permanently", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "webhook",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deliveries",
                        to="emu_moons.discordwebhookconfig",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="EmuInvoiceLine",
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
                ("type_id", models.PositiveIntegerField()),
                ("ore_name", models.CharField(max_length=128)),
                (
                    "moon_rarity",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("r4", "R4"),
                            ("r8", "R8"),
                            ("r16", "R16"),
                            ("r32", "R32"),
                            ("r64", "R64"),
                            ("unknown", "Unknown"),
                        ],
                        max_length=16,
                    ),
                ),
                ("goo_type", models.CharField(blank=True, max_length=64)),
                (
                    "tax_rate_percent",
                    models.DecimalField(decimal_places=2, default=0, max_digits=6),
                ),
                ("quantity", models.BigIntegerField()),
                (
                    "volume_m3",
                    models.DecimalField(decimal_places=4, default=0, max_digits=20),
                ),
                (
                    "material_value_isk",
                    models.DecimalField(decimal_places=2, default=0, max_digits=20),
                ),
                (
                    "tax_due_isk",
                    models.DecimalField(decimal_places=2, default=0, max_digits=20),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lines",
                        to="emu_moons.emuinvoice",
                    ),
                ),
                (
                    "price_snapshot",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="emu_moons.orepricesnapshot",
                    ),
                ),
            ],
            options={"ordering": ["ore_name"]},
        ),
        migrations.AddIndex(
            model_name="orepricesnapshot",
            index=models.Index(
                fields=["type_id", "-snapshot_at"], name="emu_moons_o_type_id_8a0f0d_idx"
            ),
        ),
    ]
