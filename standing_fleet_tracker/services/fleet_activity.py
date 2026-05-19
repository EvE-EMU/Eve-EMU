"""Determine fleet / standing-fleet context at a point in time."""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from standing_fleet_tracker.models import FleetSession


def fleet_flags_at(character, when=None) -> tuple[bool, bool]:
    """Return (in_any_fleet, in_standing_fleet) at datetime `when` (default now)."""
    when = when or timezone.now()
    session = (
        FleetSession.objects.filter(character=character, started_at__lte=when)
        .filter(Q(ended_at__isnull=True) | Q(ended_at__gte=when))
        .order_by("-started_at")
        .first()
    )
    if not session:
        return False, False
    return True, bool(session.is_standing_fleet)
