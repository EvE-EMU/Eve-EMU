from __future__ import annotations

import os

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


def default_buyback_program_id() -> int:
    raw = os.environ.get("MOON_RENTALS_BUYBACK_PROGRAM_ID", "3").strip()
    try:
        return int(raw)
    except ValueError:
        return 3


class General(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("view_schedule", "Can view moon pop schedule and compliance."),
            ("manage_schedule", "Can import and edit moon pop schedule."),
        )


class MoonPop(models.Model):
    CORP_FALSE_GODS = "corp"
    PRIVATE = "private"
    KIND_CHOICES = (
        (CORP_FALSE_GODS, "False Gods corp moon"),
        (PRIVATE, "Private rental"),
    )

    location_label = models.CharField(
        max_length=128,
        help_text="e.g. 9SBB-9 VII - Moon 20",
    )
    system_name = models.CharField(max_length=64, db_index=True)
    moon_number = models.PositiveSmallIntegerField(null=True, blank=True)
    pop_at = models.DateTimeField(db_index=True)
    rental_kind = models.CharField(max_length=16, choices=KIND_CHOICES, db_index=True)
    private_owner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="private_moon_pops",
        help_text="Required for private rentals (who must return ore via buyback).",
    )
    buyback_program_id = models.PositiveIntegerField(default=default_buyback_program_id)
    compliance_window_hours = models.PositiveIntegerField(
        default=168,
        help_text="Hours after pop to look for mining + buyback activity.",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pop_at", "system_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["location_label", "pop_at"],
                name="moon_rentals_unique_pop",
            )
        ]

    def __str__(self) -> str:
        return f"{self.location_label} @ {self.pop_at}"

    @property
    def buyback_calculate_url_path(self) -> str:
        return f"/buybackprogram/program/{self.buyback_program_id}/calculate/"

    def compliance_deadline(self):
        return self.pop_at + timezone.timedelta(hours=self.compliance_window_hours)


class MoonPopMinerStatus(models.Model):
    """Cached compliance row per miner for a scheduled pop (refreshed on demand)."""

    STATUS_PENDING = "pending"
    STATUS_QUOTED = "quoted"
    STATUS_CONTRACTED = "contracted"
    STATUS_NONE = "no_activity"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Mined — no buyback quote yet"),
        (STATUS_QUOTED, "Buyback quoted — no in-game contract"),
        (STATUS_CONTRACTED, "In-game contract linked"),
        (STATUS_NONE, "No mining seen in window"),
    )

    moon_pop = models.ForeignKey(
        MoonPop, on_delete=models.CASCADE, related_name="miner_statuses"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    character_name = models.CharField(max_length=128, blank=True)
    mined_quantity = models.PositiveBigIntegerField(default=0)
    ore_summary = models.JSONField(default=dict, blank=True)
    buyback_status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_NONE
    )
    tracking_id = models.PositiveIntegerField(null=True, blank=True)
    tracking_number = models.CharField(max_length=32, blank=True)
    contract_id = models.BigIntegerField(null=True, blank=True)
    has_compressed = models.BooleanField(default=False)
    has_uncompressed = models.BooleanField(default=False)
    refreshed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("moon_pop", "user")]
        ordering = ["-mined_quantity", "character_name"]

    def __str__(self) -> str:
        return f"{self.moon_pop_id}:{self.user_id} ({self.buyback_status})"
