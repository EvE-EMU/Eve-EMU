from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("standing_fleet_tracker", "0002_fleetsession_fleet_label_snapshot"),
        ("eveonline", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="characterscore",
            name="pulse_points",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Points from fleet pulse attendance (any fleet); not standing fleet hours.",
                max_digits=12,
            ),
        ),
        migrations.CreateModel(
            name="FleetPulse",
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
                ("fleet_id", models.BigIntegerField(db_index=True)),
                ("pulsed_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("is_standing_fleet", models.BooleanField(default=False)),
                ("member_count", models.PositiveIntegerField(default=0)),
                (
                    "members_source",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="esi_members, tracked_sessions, or mixed",
                        max_length=32,
                    ),
                ),
                (
                    "polled_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="standing_fleet_pulses_started",
                        to="eveonline.evecharacter",
                    ),
                ),
            ],
            options={
                "ordering": ["-pulsed_at"],
            },
        ),
        migrations.CreateModel(
            name="FleetPulseMember",
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
                ("eve_character_id", models.BigIntegerField(db_index=True)),
                ("role", models.CharField(blank=True, default="", max_length=32)),
                ("wing_id", models.BigIntegerField(blank=True, null=True)),
                ("squad_id", models.BigIntegerField(blank=True, null=True)),
                ("join_time", models.DateTimeField(blank=True, null=True)),
                (
                    "pulse_points_awarded",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Pulse points granted for this pulse (not standing fleet hours).",
                        max_digits=10,
                    ),
                ),
                (
                    "character",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="standing_fleet_pulse_rows",
                        to="eveonline.evecharacter",
                    ),
                ),
                (
                    "pulse",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="standing_fleet_tracker.fleetpulse",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="fleetpulse",
            index=models.Index(fields=["fleet_id", "-pulsed_at"], name="standing_fl_fleet_i_8a1f2d_idx"),
        ),
        migrations.AddIndex(
            model_name="fleetpulsemember",
            index=models.Index(fields=["eve_character_id", "-pulse_id"], name="standing_fl_charact_4c9e1a_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="fleetpulsemember",
            unique_together={("pulse", "eve_character_id")},
        ),
    ]
