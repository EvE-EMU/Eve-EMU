# Generated manually for ship fit snapshots and monthly KPIs

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("standing_fleet_tracker", "0004_fleetsessionshiplog"),
        ("eveonline", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShipFitSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ship_item_id", models.BigIntegerField()),
                ("ship_type_id", models.IntegerField(db_index=True)),
                ("ship_name", models.CharField(blank=True, default="", max_length=255)),
                ("modules_json", models.JSONField(default=list)),
                ("modules_fingerprint", models.CharField(db_index=True, max_length=64)),
                ("eft_text", models.TextField(blank=True, default="")),
                ("in_standing_fleet", models.BooleanField(default=False)),
                ("recorded_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="standing_fleet_fit_snapshots",
                        to="eveonline.evecharacter",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fit_snapshots",
                        to="standing_fleet_tracker.fleetsession",
                    ),
                ),
            ],
            options={
                "ordering": ["-recorded_at"],
            },
        ),
        migrations.AddIndex(
            model_name="shipfitsnapshot",
            index=models.Index(fields=["character", "ship_name", "-recorded_at"], name="standing_fl_charact_snap_name_idx"),
        ),
        migrations.AddIndex(
            model_name="shipfitsnapshot",
            index=models.Index(fields=["session", "-recorded_at"], name="standing_fl_session_snap_idx"),
        ),
        migrations.CreateModel(
            name="WalletJournalEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("journal_id", models.BigIntegerField()),
                ("ref_type", models.CharField(db_index=True, max_length=64)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("description", models.CharField(blank=True, default="", max_length=512)),
                ("recorded_at", models.DateTimeField(db_index=True)),
                ("in_fleet", models.BooleanField(default=False)),
                ("in_standing_fleet", models.BooleanField(default=False)),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="standing_fleet_wallet_entries",
                        to="eveonline.evecharacter",
                    ),
                ),
            ],
            options={
                "ordering": ["-recorded_at"],
                "unique_together": {("character", "journal_id")},
            },
        ),
        migrations.CreateModel(
            name="MiningLedgerEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ledger_date", models.DateField(db_index=True)),
                ("type_id", models.IntegerField()),
                ("quantity", models.BigIntegerField()),
                ("solar_system_id", models.IntegerField()),
                ("in_fleet", models.BooleanField(default=False)),
                ("in_standing_fleet", models.BooleanField(default=False)),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="standing_fleet_mining_entries",
                        to="eveonline.evecharacter",
                    ),
                ),
            ],
            options={
                "ordering": ["-ledger_date"],
                "unique_together": {("character", "ledger_date", "type_id", "solar_system_id")},
            },
        ),
        migrations.CreateModel(
            name="CharacterMonthlyKPI",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveSmallIntegerField()),
                ("month", models.PositiveSmallIntegerField()),
                ("avg_ship_group_name", models.CharField(blank=True, default="", max_length=128)),
                ("avg_region_name", models.CharField(blank=True, default="", max_length=128)),
                ("pct_standing_fleet", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("isk_ratting_in_fleet", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("isk_ratting_out_fleet", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("ratting_isk_pct_diff", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("mining_m3_standing_fleet", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("mining_m3_outside_fleet", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("computed_at", models.DateTimeField(auto_now=True)),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="standing_fleet_monthly_kpis",
                        to="eveonline.evecharacter",
                    ),
                ),
            ],
            options={
                "ordering": ["-year", "-month"],
                "unique_together": {("character", "year", "month")},
            },
        ),
    ]
