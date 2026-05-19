import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("eveonline", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StandingFleetPermissions",
            fields=[],
            options={
                "permissions": [
                    ("basic_access", "Can access standing fleet tracker"),
                    ("manage_standing_fleet", "Can manage standing fleet configuration"),
                ],
                "managed": False,
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="StandingFleetAllowlist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fleet_id", models.BigIntegerField(unique=True)),
                ("label", models.CharField(blank=True, default="", max_length=128)),
                ("notes", models.TextField(blank=True, default="")),
            ],
        ),
        migrations.CreateModel(
            name="SovSystemCache",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("alliance_id", models.IntegerField()),
                ("solar_system_id", models.IntegerField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"unique_together": {("alliance_id", "solar_system_id")}},
        ),
        migrations.CreateModel(
            name="FleetSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fleet_id", models.BigIntegerField()),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("is_standing_fleet", models.BooleanField(default=False)),
                ("classification", models.CharField(blank=True, default="", max_length=64)),
                ("fleet_commander_id", models.BigIntegerField(blank=True, null=True)),
                ("motd_snapshot", models.TextField(blank=True, default="")),
                ("last_ship_type_id", models.IntegerField(blank=True, null=True)),
                ("last_ship_name", models.CharField(blank=True, default="", max_length=255)),
                ("standing_seconds_accrued", models.PositiveIntegerField(default=0)),
                ("roam_seconds_accrued", models.PositiveIntegerField(default=0)),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="standing_fleet_sessions",
                        to="eveonline.evecharacter",
                    ),
                ),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.CreateModel(
            name="CharacterScore",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("total_points", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("standing_fleet_hours", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("penalty_hours", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("kill_bonus_points", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("last_polled_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "character",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="standing_fleet_score",
                        to="eveonline.evecharacter",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ShipFleetStat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ship_type_id", models.IntegerField()),
                ("ship_name", models.CharField(blank=True, default="", max_length=255)),
                ("seconds_flown", models.PositiveIntegerField(default=0)),
                ("session_count", models.PositiveIntegerField(default=0)),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="standing_fleet_ship_stats",
                        to="eveonline.evecharacter",
                    ),
                ),
            ],
            options={"unique_together": {("character", "ship_type_id")}, "ordering": ["-seconds_flown"]},
        ),
        migrations.CreateModel(
            name="PointLedger",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("standing_hour", "Standing fleet hour"), ("kill_bonus", "Home defence kill bonus"), ("sov_roam_penalty", "Sov roam penalty (not in standing fleet)")], max_length=32)),
                ("points", models.DecimalField(decimal_places=2, max_digits=12)),
                ("description", models.CharField(blank=True, default="", max_length=512)),
                ("period_start", models.DateTimeField(blank=True, null=True)),
                ("period_end", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "character",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="standing_fleet_point_entries",
                        to="eveonline.evecharacter",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="standing_fleet_points",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="FleetLocationSample",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("solar_system_id", models.IntegerField()),
                ("recorded_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("in_standing_fleet", models.BooleanField(default=False)),
                ("in_sov_space", models.BooleanField(default=False)),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="standing_fleet_locations",
                        to="eveonline.evecharacter",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="locations",
                        to="standing_fleet_tracker.fleetsession",
                    ),
                ),
            ],
            options={"ordering": ["-recorded_at"]},
        ),
        migrations.CreateModel(
            name="FleetKillmail",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("killmail_id", models.BigIntegerField(unique=True)),
                ("killmail_hash", models.CharField(max_length=64)),
                ("solar_system_id", models.IntegerField(blank=True, null=True)),
                ("ship_type_id", models.IntegerField(blank=True, null=True)),
                ("victim_character_id", models.BigIntegerField(blank=True, null=True)),
                ("is_home_defence", models.BooleanField(default=False)),
                ("points_awarded", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("killed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="standing_fleet_kills",
                        to="eveonline.evecharacter",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="killmails",
                        to="standing_fleet_tracker.fleetsession",
                    ),
                ),
            ],
            options={"ordering": ["-killed_at", "-created_at"]},
        ),
        migrations.AddIndex(
            model_name="fleetsession",
            index=models.Index(fields=["character", "-started_at"], name="standing_fl_charact_0a8f0d_idx"),
        ),
        migrations.AddIndex(
            model_name="fleetsession",
            index=models.Index(fields=["fleet_id", "-started_at"], name="standing_fl_fleet_i_4c2f8a_idx"),
        ),
        migrations.AddIndex(
            model_name="pointledger",
            index=models.Index(fields=["user", "-created_at"], name="standing_fl_user_id_8c1e2b_idx"),
        ),
        migrations.AddIndex(
            model_name="pointledger",
            index=models.Index(fields=["character", "-created_at"], name="standing_fl_charact_9d3e4f_idx"),
        ),
        migrations.AddIndex(
            model_name="fleetlocationsample",
            index=models.Index(fields=["character", "-recorded_at"], name="standing_fl_charact_1b2c3d_idx"),
        ),
        migrations.AddIndex(
            model_name="sovsystemcache",
            index=models.Index(fields=["alliance_id", "solar_system_id"], name="standing_fl_allianc_5e6f7a_idx"),
        ),
    ]
