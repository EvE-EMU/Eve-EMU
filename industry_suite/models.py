from __future__ import annotations

from django.db import models


class IndustrialProject(models.Model):
    """Coalition- or corp-scoped build imported from ESI (or entered manually)."""

    name = models.CharField(max_length=256)
    esi_corporation_id = models.BigIntegerField()
    esi_external_ref = models.CharField(
        max_length=128,
        blank=True,
        help_text="Opaque id from ESI (e.g. corporation project id) when available.",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.name} ({self.esi_corporation_id})"


class IndustrialSubOrder(models.Model):
    """Single claimable slice of a massive build (sub-order)."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLAIMED = "claimed", "Claimed"
        IN_PROGRESS = "in_progress", "In progress"
        DONE_ESI = "done_esi", "Verified complete (ESI)"
        CANCELLED = "cancelled", "Cancelled"

    project = models.ForeignKey(IndustrialProject, on_delete=models.CASCADE, related_name="sub_orders")
    label = models.CharField(max_length=256)
    quantity = models.PositiveIntegerField(default=1)
    type_id = models.PositiveIntegerField(null=True, blank=True, help_text="SDE type id when known.")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.OPEN)
    claimed_by_discord_id = models.BigIntegerField(null=True, blank=True)
    claimed_by_character_id = models.PositiveIntegerField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("project", "id")

    def __str__(self) -> str:
        return f"{self.label} ×{self.quantity}"


class BlueprintCopyListing(models.Model):
    """Index row for a blueprint copy available to members (BPC service)."""

    owner_label = models.CharField(max_length=128, help_text="Display only; link to AA user in a later migration.")
    type_id = models.PositiveIntegerField()
    runs_remaining = models.PositiveIntegerField(null=True, blank=True)
    material_efficiency = models.PositiveSmallIntegerField(default=0)
    time_efficiency = models.PositiveSmallIntegerField(default=0)
    is_available = models.BooleanField(default=True)
    location_note = models.CharField(max_length=256, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("type_id", "id")

    def __str__(self) -> str:
        return f"BPC {self.type_id} ({self.owner_label})"
