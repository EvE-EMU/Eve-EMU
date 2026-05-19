from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("standing_fleet_tracker", "0003_fleet_pulse"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="characterscore",
            options={
                "verbose_name": "Character standing fleet score",
                "verbose_name_plural": "Character standing fleet scores",
            },
        ),
        migrations.AlterField(
            model_name="pointledger",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("standing_hour", "Standing fleet hour"),
                    ("pulse_attendance", "Fleet pulse attendance"),
                    ("kill_bonus", "Home defence kill bonus"),
                    ("sov_roam_penalty", "Sov roam penalty (not in standing fleet)"),
                ],
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="FleetSessionShipLog",
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
                ("ship_type_id", models.IntegerField()),
                ("ship_name", models.CharField(blank=True, default="", max_length=255)),
                (
                    "recorded_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ship_log",
                        to="standing_fleet_tracker.fleetsession",
                    ),
                ),
            ],
            options={
                "ordering": ["recorded_at"],
            },
        ),
        migrations.AddIndex(
            model_name="fleetsessionshiplog",
            index=models.Index(
                fields=["session", "recorded_at"],
                name="standing_fl_session_7c4a21_idx",
            ),
        ),
    ]
