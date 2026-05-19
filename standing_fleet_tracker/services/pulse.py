"""Fleet pulse: roster snapshot + pulse points (separate from standing fleet hours)."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from allianceauth.eveonline.models import EveCharacter

from standing_fleet_tracker import app_settings
from standing_fleet_tracker.models import (
    FleetPulse,
    FleetPulseMember,
    FleetSession,
    PointEventType,
    PointLedger,
)
from standing_fleet_tracker.services import esi as esi_api
from standing_fleet_tracker.services.scoring import _bump_character_score, _user_for_character

logger = logging.getLogger(__name__)


def _pulse_cache_key(fleet_id: int) -> str:
    return f"sft:fleet_pulse:{fleet_id}"


def _resolve_eve_character(character_id: int) -> EveCharacter | None:
    return EveCharacter.objects.filter(character_id=character_id).first()


def _members_from_open_sessions(fleet_id: int) -> list[dict]:
    rows = []
    for session in FleetSession.objects.filter(
        fleet_id=fleet_id,
        ended_at__isnull=True,
    ).select_related("character"):
        rows.append(
            {
                "character_id": session.character.character_id,
                "role": "",
                "wing_id": None,
                "squad_id": None,
                "join_time": session.started_at.isoformat(),
            }
        )
    return rows


def record_fleet_pulse(
    *,
    fleet_id: int,
    token,
    fleet_boss_id: int | None,
    polled_by: EveCharacter,
    is_standing_fleet: bool,
) -> FleetPulse | None:
    """
    At most one pulse per fleet per poll interval.

    Records all visible members and awards pulse points to linked Auth characters.
    Does not award standing fleet hour points.
    """
    interval = max(60, app_settings.SFT_POLL_INTERVAL_SECONDS)
    if not cache.add(_pulse_cache_key(fleet_id), 1, timeout=interval):
        return None

    esi_members = esi_api.get_fleet_members(
        fleet_id,
        token,
        fleet_boss_id=fleet_boss_id,
    )
    source = "esi_members"
    if esi_members:
        roster = esi_members
    else:
        roster = _members_from_open_sessions(fleet_id)
        source = "tracked_sessions" if roster else "none"

    if not roster:
        roster = [
            {
                "character_id": polled_by.character_id,
                "role": "",
                "wing_id": None,
                "squad_id": None,
                "join_time": None,
            }
        ]
        source = "polled_character"

    pulse = FleetPulse.objects.create(
        fleet_id=fleet_id,
        pulsed_at=timezone.now(),
        is_standing_fleet=is_standing_fleet,
        member_count=len(roster),
        polled_by=polled_by,
        members_source=source,
    )

    pts_each = Decimal(str(app_settings.SFT_PULSE_POINTS_PER_PULSE))
    awarded = 0

    for row in roster:
        char_id = row.get("character_id")
        if not char_id:
            continue
        char_id = int(char_id)
        eve_char = _resolve_eve_character(char_id)
        join_raw = row.get("join_time")
        join_time = parse_datetime(str(join_raw)) if join_raw else None

        member, _ = FleetPulseMember.objects.get_or_create(
            pulse=pulse,
            eve_character_id=char_id,
            defaults={
                "character": eve_char,
                "role": str(row.get("role") or "")[:32],
                "wing_id": row.get("wing_id"),
                "squad_id": row.get("squad_id"),
                "join_time": join_time,
            },
        )

        user = _user_for_character(eve_char) if eve_char else None
        if not user or pts_each <= 0:
            continue

        PointLedger.objects.create(
            user=user,
            character=eve_char,
            event_type=PointEventType.PULSE_ATTENDANCE,
            points=pts_each,
            description=f"Fleet pulse {fleet_id} (pulse #{pulse.pk})",
            period_start=pulse.pulsed_at,
            period_end=pulse.pulsed_at,
        )
        member.pulse_points_awarded = pts_each
        member.save(update_fields=["pulse_points_awarded"])
        if eve_char:
            _bump_character_score(eve_char, pulse_delta=pts_each, points_delta=pts_each)
        awarded += 1

    logger.info(
        "SFT pulse fleet %s: %s members, %s pulse points awarded, standing=%s",
        fleet_id,
        len(roster),
        awarded,
        is_standing_fleet,
    )
    return pulse
