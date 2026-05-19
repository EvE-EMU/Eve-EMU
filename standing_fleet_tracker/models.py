from django.conf import settings
from django.db import models
from django.utils import timezone


class PointEventType(models.TextChoices):
    STANDING_HOUR = "standing_hour", "Standing fleet hour"
    PULSE_ATTENDANCE = "pulse_attendance", "Fleet pulse attendance"
    KILL_BONUS = "kill_bonus", "Home defence kill bonus"
    SOV_ROAM_PENALTY = "sov_roam_penalty", "Sov roam penalty (not in standing fleet)"


class StandingFleetPermissions(models.Model):
    """Placeholder for custom permissions."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("basic_access", "Can access standing fleet tracker"),
            ("manage_standing_fleet", "Can manage standing fleet configuration"),
        ]


class FleetSession(models.Model):
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="standing_fleet_sessions",
    )
    fleet_id = models.BigIntegerField()
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_standing_fleet = models.BooleanField(default=False)
    classification = models.CharField(max_length=64, blank=True, default="")
    fleet_commander_id = models.BigIntegerField(null=True, blank=True)
    motd_snapshot = models.TextField(blank=True, default="")
    fleet_label_snapshot = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Fleet advert / AFAT name when MOTD is unavailable to members.",
    )
    last_ship_type_id = models.IntegerField(null=True, blank=True)
    last_ship_name = models.CharField(max_length=255, blank=True, default="")
    standing_seconds_accrued = models.PositiveIntegerField(default=0)
    roam_seconds_accrued = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(
                fields=["character", "-started_at"],
                name="standing_fl_charact_0a8f0d_idx",
            ),
            models.Index(
                fields=["fleet_id", "-started_at"],
                name="standing_fl_fleet_i_4c2f8a_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.character} fleet {self.fleet_id}"


class FleetLocationSample(models.Model):
    session = models.ForeignKey(
        FleetSession,
        on_delete=models.CASCADE,
        related_name="locations",
        null=True,
        blank=True,
    )
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="standing_fleet_locations",
    )
    solar_system_id = models.IntegerField()
    recorded_at = models.DateTimeField(default=timezone.now)
    in_standing_fleet = models.BooleanField(default=False)
    in_sov_space = models.BooleanField(default=False)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(
                fields=["character", "-recorded_at"],
                name="standing_fl_charact_1b2c3d_idx",
            ),
        ]


class FleetPulse(models.Model):
    """One roster snapshot per fleet per poll interval (pulse)."""

    fleet_id = models.BigIntegerField(db_index=True)
    pulsed_at = models.DateTimeField(default=timezone.now, db_index=True)
    is_standing_fleet = models.BooleanField(default=False)
    member_count = models.PositiveIntegerField(default=0)
    polled_by = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="standing_fleet_pulses_started",
    )
    members_source = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="esi_members, tracked_sessions, or mixed",
    )

    class Meta:
        ordering = ["-pulsed_at"]
        indexes = [
            models.Index(
                fields=["fleet_id", "-pulsed_at"],
                name="standing_fl_fleet_i_8a1f2d_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Pulse fleet {self.fleet_id} @ {self.pulsed_at}"


class FleetPulseMember(models.Model):
    pulse = models.ForeignKey(
        FleetPulse,
        on_delete=models.CASCADE,
        related_name="members",
    )
    eve_character_id = models.BigIntegerField(db_index=True)
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="standing_fleet_pulse_rows",
    )
    role = models.CharField(max_length=32, blank=True, default="")
    wing_id = models.BigIntegerField(null=True, blank=True)
    squad_id = models.BigIntegerField(null=True, blank=True)
    join_time = models.DateTimeField(null=True, blank=True)
    pulse_points_awarded = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Pulse points granted for this pulse (not standing fleet hours).",
    )

    class Meta:
        unique_together = [("pulse", "eve_character_id")]
        indexes = [
            models.Index(
                fields=["eve_character_id", "-pulse_id"],
                name="standing_fl_charact_4c9e1a_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.eve_character_id} in pulse {self.pulse_id}"


class FleetSessionShipLog(models.Model):
    """Ship flown during a fleet session (recorded when ship is seen or changes)."""

    session = models.ForeignKey(
        FleetSession,
        on_delete=models.CASCADE,
        related_name="ship_log",
    )
    ship_type_id = models.IntegerField()
    ship_name = models.CharField(max_length=255, blank=True, default="")
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["recorded_at"]
        indexes = [
            models.Index(
                fields=["session", "recorded_at"],
                name="standing_fl_session_7c4a21_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.ship_name or self.ship_type_id} @ {self.recorded_at}"


class FleetKillmail(models.Model):
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="standing_fleet_kills",
    )
    session = models.ForeignKey(
        FleetSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="killmails",
    )
    killmail_id = models.BigIntegerField(unique=True)
    killmail_hash = models.CharField(max_length=64)
    solar_system_id = models.IntegerField(null=True, blank=True)
    ship_type_id = models.IntegerField(null=True, blank=True)
    victim_character_id = models.BigIntegerField(null=True, blank=True)
    is_home_defence = models.BooleanField(default=False)
    points_awarded = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    killed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-killed_at", "-created_at"]


class PointLedger(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="standing_fleet_points",
    )
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="standing_fleet_point_entries",
    )
    event_type = models.CharField(max_length=32, choices=PointEventType.choices)
    points = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=512, blank=True, default="")
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "-created_at"],
                name="standing_fl_user_id_8c1e2b_idx",
            ),
            models.Index(
                fields=["character", "-created_at"],
                name="standing_fl_charact_9d3e4f_idx",
            ),
        ]


class CharacterScore(models.Model):
    """Materialized totals per character (rolled up to user in views)."""

    character = models.OneToOneField(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="standing_fleet_score",
    )
    total_points = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    standing_fleet_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    penalty_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    kill_bonus_points = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pulse_points = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Points from fleet pulse attendance (any fleet); not standing fleet hours.",
    )
    last_polled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Character standing fleet score"
        verbose_name_plural = "Character standing fleet scores"


class ShipFleetStat(models.Model):
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="standing_fleet_ship_stats",
    )
    ship_type_id = models.IntegerField()
    ship_name = models.CharField(max_length=255, blank=True, default="")
    seconds_flown = models.PositiveIntegerField(default=0)
    session_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("character", "ship_type_id")]
        ordering = ["-seconds_flown"]


class StandingFleetAllowlist(models.Model):
    fleet_id = models.BigIntegerField(unique=True)
    label = models.CharField(max_length=128, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return self.label or str(self.fleet_id)


class ShipFitSnapshot(models.Model):
    """Point-in-time fitted ship modules (retained ~90 days)."""

    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="standing_fleet_fit_snapshots",
    )
    session = models.ForeignKey(
        FleetSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fit_snapshots",
    )
    ship_item_id = models.BigIntegerField()
    ship_type_id = models.IntegerField()
    ship_name = models.CharField(max_length=255, blank=True, default="")
    modules_json = models.JSONField(default=list)
    modules_fingerprint = models.CharField(max_length=64, db_index=True)
    eft_text = models.TextField(blank=True, default="")
    in_standing_fleet = models.BooleanField(default=False)
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["character", "ship_name", "-recorded_at"]),
            models.Index(fields=["session", "-recorded_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.ship_name or self.ship_type_id} @ {self.recorded_at}"


class WalletJournalEntry(models.Model):
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="standing_fleet_wallet_entries",
    )
    journal_id = models.BigIntegerField()
    ref_type = models.CharField(max_length=64, db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    description = models.CharField(max_length=512, blank=True, default="")
    recorded_at = models.DateTimeField(db_index=True)
    in_fleet = models.BooleanField(default=False)
    in_standing_fleet = models.BooleanField(default=False)

    class Meta:
        unique_together = [("character", "journal_id")]
        ordering = ["-recorded_at"]


class MiningLedgerEntry(models.Model):
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="standing_fleet_mining_entries",
    )
    ledger_date = models.DateField(db_index=True)
    type_id = models.IntegerField()
    quantity = models.BigIntegerField()
    solar_system_id = models.IntegerField()
    in_fleet = models.BooleanField(default=False)
    in_standing_fleet = models.BooleanField(default=False)

    class Meta:
        unique_together = [("character", "ledger_date", "type_id", "solar_system_id")]
        ordering = ["-ledger_date"]


class CharacterMonthlyKPI(models.Model):
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="standing_fleet_monthly_kpis",
    )
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    avg_ship_group_name = models.CharField(max_length=128, blank=True, default="")
    avg_region_name = models.CharField(max_length=128, blank=True, default="")
    pct_standing_fleet = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    isk_ratting_in_fleet = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    isk_ratting_out_fleet = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    ratting_isk_pct_diff = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    mining_m3_standing_fleet = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    mining_m3_outside_fleet = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("character", "year", "month")]
        ordering = ["-year", "-month"]


class SovSystemCache(models.Model):
    alliance_id = models.IntegerField()
    solar_system_id = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("alliance_id", "solar_system_id")]
        indexes = [
            models.Index(
                fields=["alliance_id", "solar_system_id"],
                name="standing_fl_allianc_5e6f7a_idx",
            ),
        ]
