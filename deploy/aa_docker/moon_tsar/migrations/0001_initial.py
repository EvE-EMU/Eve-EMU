# Generated for Moon Tsar initial schema

import uuid
from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MoonTsarSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("corporation_id", models.BigIntegerField(default=98799892)),
                ("wallet_division", models.PositiveSmallIntegerField(default=1)),
                ("tracking_hours_after_pop", models.PositiveSmallIntegerField(default=20)),
                ("tax_payment_phrase", models.CharField(default="MOON-TAX", max_length=32)),
                ("tax_isk_recipient_character_id", models.BigIntegerField(blank=True, null=True)),
                ("mineral_contract_corp_id", models.BigIntegerField(blank=True, null=True)),
                ("discord_webhook_url", models.URLField(blank=True, max_length=512)),
                ("bill_due_days_after_pop", models.PositiveSmallIntegerField(default=30)),
                ("esi_token_id", models.PositiveIntegerField(blank=True, null=True)),
                ("site_name_override", models.CharField(blank=True, max_length=64)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Moon Tsar settings"},
        ),
        migrations.CreateModel(
            name="MoonOreTaxRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type_id", models.PositiveIntegerField(unique=True)),
                ("type_name", models.CharField(max_length=128)),
                ("tax_rate_percent", models.DecimalField(decimal_places=2, default=Decimal("10.00"), max_digits=6)),
                ("use_adjusted_price", models.BooleanField(default=True)),
                ("active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["type_name"], "verbose_name": "moon ore tax rate"},
        ),
        migrations.CreateModel(
            name="MoonExtractionEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("moonmining_extraction_id", models.PositiveIntegerField(blank=True, null=True, unique=True)),
                ("moon_label", models.CharField(max_length=255)),
                ("system_name", models.CharField(blank=True, max_length=128)),
                ("moon_number", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("structure_name", models.CharField(blank=True, max_length=255)),
                ("popped_at", models.DateTimeField()),
                ("tracking_ends_at", models.DateTimeField()),
                ("ledger_synced_at", models.DateTimeField(blank=True, null=True)),
                ("bills_generated_at", models.DateTimeField(blank=True, null=True)),
                ("total_mined_m3", models.BigIntegerField(default=0)),
                ("total_ore_isk", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("total_tax_isk", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-popped_at"]},
        ),
        migrations.CreateModel(
            name="MoonRentalProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("moon_label", models.CharField(max_length=255, unique=True)),
                ("moonmining_moon_id", models.PositiveIntegerField(blank=True, null=True)),
                ("renter_corporation_id", models.BigIntegerField(blank=True, null=True)),
                ("renter_corporation_name", models.CharField(blank=True, max_length=255)),
                ("monthly_rent_isk", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("rent_payment_phrase", models.CharField(default="MOON-RENT-PRIVATE", max_length=64)),
                ("custom_tax_rates_json", models.JSONField(blank=True, default=dict)),
                ("active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "renter_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="rented_moons",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MoonProfitabilitySnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("snapshot_date", models.DateField()),
                ("total_mined_isk", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("total_tax_isk", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("total_fuel_isk", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("net_isk", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("extraction_count", models.PositiveIntegerField(default=0)),
                ("meta_json", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ["-snapshot_date"], "unique_together": {("snapshot_date",)}},
        ),
        migrations.CreateModel(
            name="MoonHeatmapCell",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("system_name", models.CharField(max_length=128)),
                ("moon_number", models.PositiveSmallIntegerField()),
                ("moon_label", models.CharField(max_length=255)),
                ("mined_m3", models.BigIntegerField(default=0)),
                ("expected_m3", models.BigIntegerField(default=0)),
                ("extraction_count", models.PositiveIntegerField(default=0)),
                ("performance_score", models.FloatField(default=0.0)),
            ],
            options={
                "ordering": ["-performance_score"],
                "unique_together": {("period_start", "period_end", "moon_label")},
            },
        ),
        migrations.CreateModel(
            name="MoonTaxBill",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("character_id", models.BigIntegerField()),
                ("character_name", models.CharField(blank=True, max_length=128)),
                ("status", models.CharField(choices=[("open", "Open"), ("partial", "Partially paid"), ("paid", "Paid"), ("void", "Void")], default="open", max_length=16)),
                ("due_date", models.DateField()),
                ("total_m3", models.DecimalField(decimal_places=4, default=0, max_digits=20)),
                ("total_gross_isk", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("total_tax_isk", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("amount_paid_isk", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("line_summary_json", models.JSONField(blank=True, default=list)),
                ("reminder_30d_sent", models.DateTimeField(blank=True, null=True)),
                ("reminder_7d_sent", models.DateTimeField(blank=True, null=True)),
                ("reminder_1d_sent", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                (
                    "extraction",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bills",
                        to="moon_tsar.moonextractionevent",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="moon_tax_bills",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-due_date", "character_name"], "unique_together": {("extraction", "user")}},
        ),
        migrations.CreateModel(
            name="MoonExtractionLedgerLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("miner_character_id", models.BigIntegerField()),
                ("miner_character_name", models.CharField(blank=True, max_length=128)),
                ("type_id", models.PositiveIntegerField()),
                ("type_name", models.CharField(blank=True, max_length=128)),
                ("quantity", models.BigIntegerField()),
                ("volume_m3", models.DecimalField(decimal_places=4, default=0, max_digits=20)),
                ("gross_isk", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("tax_isk", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("observer_log_id", models.PositiveIntegerField(blank=True, null=True, unique=True)),
                ("mined_at", models.DateField()),
                (
                    "extraction",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ledger_lines",
                        to="moon_tsar.moonextractionevent",
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
            options={"ordering": ["-mined_at", "miner_character_name"]},
        ),
        migrations.CreateModel(
            name="MoonTaxPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("wallet", "Corp wallet donation"), ("contract", "Item exchange contract")], max_length=16)),
                ("amount_isk", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("external_id", models.CharField(blank=True, max_length=64)),
                ("note", models.CharField(blank=True, max_length=512)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "bill",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="moon_tsar.moontaxbill",
                    ),
                ),
            ],
            options={"ordering": ["-recorded_at"]},
        ),
    ]
