# Generated manually for moon_rentals

import django.db.models.deletion
import moon_rentals.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="General",
            fields=[],
            options={
                "permissions": (
                    ("view_schedule", "Can view moon pop schedule and compliance."),
                    ("manage_schedule", "Can import and edit moon pop schedule."),
                ),
                "managed": False,
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="MoonPop",
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
                    "location_label",
                    models.CharField(
                        help_text="e.g. 9SBB-9 VII - Moon 20", max_length=128
                    ),
                ),
                ("system_name", models.CharField(db_index=True, max_length=64)),
                (
                    "moon_number",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("pop_at", models.DateTimeField(db_index=True)),
                (
                    "rental_kind",
                    models.CharField(
                        choices=[
                            ("corp", "False Gods corp moon"),
                            ("private", "Private rental"),
                        ],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                (
                    "buyback_program_id",
                    models.PositiveIntegerField(
                        default=moon_rentals.models.default_buyback_program_id
                    ),
                ),
                (
                    "compliance_window_hours",
                    models.PositiveIntegerField(
                        default=168,
                        help_text="Hours after pop to look for mining + buyback activity.",
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "private_owner",
                    models.ForeignKey(
                        blank=True,
                        help_text="Required for private rentals (who must return ore via buyback).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="private_moon_pops",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["pop_at", "system_name"],
            },
        ),
        migrations.CreateModel(
            name="MoonPopMinerStatus",
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
                ("character_name", models.CharField(blank=True, max_length=128)),
                ("mined_quantity", models.PositiveBigIntegerField(default=0)),
                ("ore_summary", models.JSONField(blank=True, default=dict)),
                (
                    "buyback_status",
                    models.CharField(
                        choices=[
                            ("pending", "Mined — no buyback quote yet"),
                            ("quoted", "Buyback quoted — no in-game contract"),
                            ("contracted", "In-game contract linked"),
                            ("no_activity", "No mining seen in window"),
                        ],
                        default="no_activity",
                        max_length=16,
                    ),
                ),
                ("tracking_id", models.PositiveIntegerField(blank=True, null=True)),
                ("tracking_number", models.CharField(blank=True, max_length=32)),
                ("contract_id", models.BigIntegerField(blank=True, null=True)),
                ("has_compressed", models.BooleanField(default=False)),
                ("has_uncompressed", models.BooleanField(default=False)),
                ("refreshed_at", models.DateTimeField(auto_now=True)),
                (
                    "moon_pop",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="miner_statuses",
                        to="moon_rentals.moonpop",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-mined_quantity", "character_name"],
                "unique_together": {("moon_pop", "user")},
            },
        ),
        migrations.AddConstraint(
            model_name="moonpop",
            constraint=models.UniqueConstraint(
                fields=("location_label", "pop_at"), name="moon_rentals_unique_pop"
            ),
        ),
    ]
