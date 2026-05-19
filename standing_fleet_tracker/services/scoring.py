"""Accrue standing fleet points from sessions, kills, and sov roams."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership

from standing_fleet_tracker import app_settings
from standing_fleet_tracker.models import (
    CharacterScore,
    FleetKillmail,
    FleetLocationSample,
    FleetSession,
    PointEventType,
    PointLedger,
)

User = get_user_model()


def _user_for_character(character):
    own = CharacterOwnership.objects.filter(character=character).first()
    return own.user if own else None


def accrue_standing_hours() -> int:
    """Award +points for standing fleet time since last accrual on open/closed sessions."""
    now = timezone.now()
    created = 0
    sessions = (
        FleetSession.objects.filter(is_standing_fleet=True)
        .select_related("character")
        .order_by("-started_at")[:500]
    )

    for session in sessions:
        end = session.ended_at or now
        duration = int((end - session.started_at).total_seconds())
        already = session.standing_seconds_accrued
        delta = max(0, duration - already)
        if delta < 60:
            continue

        hours = Decimal(delta) / Decimal(3600)
        points = hours * Decimal(str(app_settings.SFT_POINTS_PER_STANDING_HOUR))
        user = _user_for_character(session.character)
        if not user:
            continue

        PointLedger.objects.create(
            user=user,
            character=session.character,
            event_type=PointEventType.STANDING_HOUR,
            points=points,
            description=f"Standing fleet {session.fleet_id} ({hours:.2f} h)",
            period_start=session.started_at,
            period_end=end,
        )
        session.standing_seconds_accrued = duration
        session.save(update_fields=["standing_seconds_accrued"])
        _bump_character_score(session.character, standing_delta=hours, points_delta=points)
        created += 1
    return created


def accrue_kill_bonuses() -> int:
    created = 0
    kills = FleetKillmail.objects.filter(
        is_home_defence=True,
        points_awarded=0,
    ).select_related("character")[:200]

    for km in kills:
        user = _user_for_character(km.character)
        if not user:
            continue
        pts = Decimal(app_settings.SFT_KILL_BONUS_POINTS)
        PointLedger.objects.create(
            user=user,
            character=km.character,
            event_type=PointEventType.KILL_BONUS,
            points=pts,
            description=f"Home defence killmail {km.killmail_id}",
            period_start=km.killed_at,
            period_end=km.killed_at,
        )
        km.points_awarded = pts
        km.save(update_fields=["points_awarded"])
        _bump_character_score(km.character, kill_delta=pts, points_delta=pts)
        created += 1
    return created


def accrue_sov_roam_penalties() -> int:
    """-1 point per hour of system-to-system movement in sov while not in standing fleet."""
    created = 0
    chars = (
        FleetLocationSample.objects.filter(in_sov_space=True, in_standing_fleet=False)
        .values_list("character_id", flat=True)
        .distinct()
    )
    for char_id in chars:
        samples = list(
            FleetLocationSample.objects.filter(character_id=char_id)
            .order_by("recorded_at")[:500]
        )
        roam_seconds = 0
        for i in range(1, len(samples)):
            prev, cur = samples[i - 1], samples[i]
            if (
                prev.in_sov_space
                and cur.in_sov_space
                and not cur.in_standing_fleet
                and prev.solar_system_id != cur.solar_system_id
            ):
                roam_seconds += int((cur.recorded_at - prev.recorded_at).total_seconds())

        if roam_seconds < 3600:
            continue

        from allianceauth.eveonline.models import EveCharacter

        character = EveCharacter.objects.get(pk=char_id)
        user = _user_for_character(character)
        if not user:
            continue

        hours = Decimal(roam_seconds) / Decimal(3600)
        points = -hours * Decimal(str(app_settings.SFT_PENALTY_PER_SOV_ROAM_HOUR))
        PointLedger.objects.create(
            user=user,
            character=character,
            event_type=PointEventType.SOV_ROAM_PENALTY,
            points=points,
            description=f"Sov roam without standing fleet ({hours:.2f} h)",
        )
        _bump_character_score(character, penalty_delta=hours, points_delta=points)
        FleetLocationSample.objects.filter(character_id=char_id, in_standing_fleet=False).delete()
        created += 1
    return created


def _bump_character_score(
    character,
    *,
    standing_delta=Decimal(0),
    penalty_delta=Decimal(0),
    kill_delta=Decimal(0),
    pulse_delta=Decimal(0),
    points_delta=Decimal(0),
) -> None:
    score, _ = CharacterScore.objects.get_or_create(character=character)
    score.standing_fleet_hours += standing_delta
    score.penalty_hours += penalty_delta
    score.kill_bonus_points += kill_delta
    score.pulse_points += pulse_delta
    score.total_points += points_delta
    score.save(
        update_fields=[
            "standing_fleet_hours",
            "penalty_hours",
            "kill_bonus_points",
            "pulse_points",
            "total_points",
            "updated_at",
        ]
    )


def rebuild_character_scores() -> int:
    count = 0
    for char_id in CharacterOwnership.objects.values_list("character_id", flat=True).distinct():
        from allianceauth.eveonline.models import EveCharacter

        character = EveCharacter.objects.get(pk=char_id)
        user = _user_for_character(character)
        if not user:
            continue
        agg = PointLedger.objects.filter(character=character).aggregate(
            total=Sum("points"),
            standing=Sum("points", filter={"event_type": PointEventType.STANDING_HOUR}),
            penalty=Sum("points", filter={"event_type": PointEventType.SOV_ROAM_PENALTY}),
            kills=Sum("points", filter={"event_type": PointEventType.KILL_BONUS}),
            pulse=Sum("points", filter={"event_type": PointEventType.PULSE_ATTENDANCE}),
        )
        CharacterScore.objects.update_or_create(
            character=character,
            defaults={
                "total_points": agg["total"] or Decimal(0),
                "standing_fleet_hours": _hours_from_points(agg["standing"]),
                "penalty_hours": _penalty_hours(character),
                "kill_bonus_points": agg["kills"] or Decimal(0),
                "pulse_points": agg["pulse"] or Decimal(0),
            },
        )
        count += 1
    return count


def _hours_from_points(points_sum) -> Decimal:
    if not points_sum:
        return Decimal(0)
    return Decimal(points_sum) / Decimal(str(app_settings.SFT_POINTS_PER_STANDING_HOUR))


def _penalty_hours(character) -> Decimal:
    agg = PointLedger.objects.filter(
        character=character,
        event_type=PointEventType.SOV_ROAM_PENALTY,
    ).aggregate(s=Sum("points"))
    pts = agg["s"] or Decimal(0)
    if pts >= 0:
        return Decimal(0)
    return abs(pts) / Decimal(str(app_settings.SFT_PENALTY_PER_SOV_ROAM_HOUR))


def user_leaderboard(limit: int = 50):
    """Aggregate character scores by auth user (sum of all owned characters)."""
    rows = []
    users = User.objects.filter(is_active=True).prefetch_related("character_ownerships__character")
    for user in users:
        char_ids = list(
            user.character_ownerships.values_list("character_id", flat=True)
        )
        if not char_ids:
            continue
        agg = CharacterScore.objects.filter(character_id__in=char_ids).aggregate(
            total=Sum("total_points"),
            standing=Sum("standing_fleet_hours"),
            penalty=Sum("penalty_hours"),
            kills=Sum("kill_bonus_points"),
            pulse=Sum("pulse_points"),
        )
        total = agg["total"] or Decimal(0)
        rows.append(
            {
                "user": user,
                "total_points": total,
                "standing_hours": agg["standing"] or Decimal(0),
                "penalty_hours": agg["penalty"] or Decimal(0),
                "kill_points": agg["kills"] or Decimal(0),
                "pulse_points": agg["pulse"] or Decimal(0),
                "main_character": getattr(user.profile, "main_character", None),
            }
        )
    rows.sort(key=lambda r: r["total_points"], reverse=True)
    return rows[:limit]
