"""Live fleet / standing status for UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter

from standing_fleet_tracker import app_settings
from standing_fleet_tracker.models import CharacterScore, FleetSession
from standing_fleet_tracker.services import esi as esi_api
from standing_fleet_tracker.services.motd_text import normalize_fleet_text
from standing_fleet_tracker.services.scopes import missing_scopes_for_token, required_scopes


@dataclass
class CharacterLiveStatus:
    character: EveCharacter
    tracked: bool
    missing_scopes: bool
    missing_scope_names: list[str]
    in_fleet: bool
    is_standing_fleet: bool
    standing_label: str
    classification: str
    fleet_id: int | None
    ship_name: str
    session_started_at: datetime | None
    session_seconds: int
    unaccrued_standing_seconds: int
    seconds_to_next_point: int
    progress_to_next_point: int
    points_per_hour: float
    last_polled_at: datetime | None
    poll_stale: bool

    @property
    def fleet_status_text(self) -> str:
        if not self.tracked:
            return "No ESI token — add this character on Alliance Auth"
        if self.missing_scopes:
            missing = ", ".join(self.missing_scope_names) or "esi-fleets.read_fleet.v1"
            return (
                f"This character's token is missing scopes ({missing}). "
                "Re-authorize this alt on Charlink with Standing Fleet Tracker enabled. "
                "You do not need to be fleet commander."
            )
        if not self.in_fleet:
            if self.poll_stale:
                return "Not in a fleet (poll data may be stale)"
            return "Not in a fleet"
        if self.is_standing_fleet:
            label = self.standing_label or "Standing"
            return f"In fleet — {label}"
        return (
            "In fleet — not classified as a standing fleet yet "
            "(MOTD/AFAT name must match WOMP/Standing; FC role not required)"
        )


def matched_motd_label(motd: str) -> str:
    normalized = normalize_fleet_text(motd)
    if not normalized:
        return ""
    upper = normalized.upper()
    for needle in app_settings.SFT_STANDING_MOTD_SUBSTRINGS:
        if needle.upper() in upper:
            return needle
    return ""


def standing_label_for_session(session: FleetSession) -> str:
    if not session.is_standing_fleet:
        return ""
    motd_label = matched_motd_label(session.motd_snapshot)
    if motd_label:
        return f"{motd_label} standing"
    label = (session.fleet_label_snapshot or "").strip()
    if label and matched_motd_label(label):
        return f"{matched_motd_label(label)} standing"
    if session.classification == "fleet_label" and label:
        return label
    if session.classification == "allowlist":
        from standing_fleet_tracker.models import StandingFleetAllowlist

        row = StandingFleetAllowlist.objects.filter(fleet_id=session.fleet_id).first()
        if row and row.label:
            return row.label
        return "Allowlisted standing"
    return "Standing fleet"


def _character_tracked(character: EveCharacter) -> tuple[bool, bool, list[str]]:
    token = esi_api.token_for_character(character.character_id)
    if not token:
        return False, True, required_scopes()
    missing = missing_scopes_for_token(token)
    return True, bool(missing), missing


def get_character_live_status(character: EveCharacter) -> CharacterLiveStatus:
    tracked, missing_scopes, missing_scope_names = _character_tracked(character)
    score = CharacterScore.objects.filter(character=character).first()
    last_polled = score.last_polled_at if score else None
    poll_interval = app_settings.SFT_POLL_INTERVAL_SECONDS
    poll_stale = bool(
        last_polled
        and (timezone.now() - last_polled).total_seconds() > poll_interval * 2
    )

    active = (
        FleetSession.objects.filter(character=character, ended_at__isnull=True)
        .order_by("-started_at")
        .first()
    )

    if not active:
        return CharacterLiveStatus(
            character=character,
            tracked=tracked,
            missing_scopes=missing_scopes,
            missing_scope_names=missing_scope_names,
            in_fleet=False,
            is_standing_fleet=False,
            standing_label="",
            classification="",
            fleet_id=None,
            ship_name="",
            session_started_at=None,
            session_seconds=0,
            unaccrued_standing_seconds=0,
            seconds_to_next_point=3600,
            progress_to_next_point=0,
            points_per_hour=app_settings.SFT_POINTS_PER_STANDING_HOUR,
            last_polled_at=last_polled,
            poll_stale=poll_stale,
        )

    now = timezone.now()
    duration = int((now - active.started_at).total_seconds())
    unaccrued = 0
    if active.is_standing_fleet:
        unaccrued = max(0, duration - int(active.standing_seconds_accrued))
    remainder = unaccrued % 3600
    seconds_to_next = 3600 - remainder if remainder else 0
    progress = int((remainder / 3600) * 100) if active.is_standing_fleet else 0

    return CharacterLiveStatus(
        character=character,
        tracked=tracked,
        missing_scopes=missing_scopes,
        missing_scope_names=missing_scope_names,
        in_fleet=True,
        is_standing_fleet=active.is_standing_fleet,
        standing_label=standing_label_for_session(active),
        classification=active.classification,
        fleet_id=active.fleet_id,
        ship_name=active.last_ship_name or "",
        session_started_at=active.started_at,
        session_seconds=duration,
        unaccrued_standing_seconds=unaccrued,
        seconds_to_next_point=seconds_to_next,
        progress_to_next_point=progress,
        points_per_hour=app_settings.SFT_POINTS_PER_STANDING_HOUR,
        last_polled_at=last_polled,
        poll_stale=poll_stale,
    )


def live_status_for_user(user) -> list[CharacterLiveStatus]:
    char_ids = CharacterOwnership.objects.filter(user=user, user__is_active=True).values_list(
        "character_id", flat=True
    )
    characters = EveCharacter.objects.filter(pk__in=char_ids).order_by("character_name")
    return [get_character_live_status(c) for c in characters]


def live_fleet_roster(*, standing_only: bool = False, limit: int = 100) -> list[CharacterLiveStatus]:
    """All characters currently in an open fleet session."""
    open_sessions = FleetSession.objects.filter(ended_at__isnull=True).select_related(
        "character"
    )[:limit]
    rows: list[CharacterLiveStatus] = []
    seen = set()
    for session in open_sessions:
        if session.character_id in seen:
            continue
        seen.add(session.character_id)
        status = get_character_live_status(session.character)
        if standing_only and not status.is_standing_fleet:
            continue
        rows.append(status)
    rows.sort(
        key=lambda s: (
            not s.is_standing_fleet,
            s.character.character_name,
        )
    )
    return rows
