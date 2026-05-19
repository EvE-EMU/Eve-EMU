"""Classify whether a fleet counts as a standing fleet."""

from __future__ import annotations

from standing_fleet_tracker import app_settings
from standing_fleet_tracker.models import StandingFleetAllowlist
from standing_fleet_tracker.services.motd_text import normalize_fleet_text


def text_matches_standing(text: str) -> bool:
    normalized = normalize_fleet_text(text)
    if not normalized:
        return False
    upper = normalized.upper()
    for needle in app_settings.SFT_STANDING_MOTD_SUBSTRINGS:
        if needle.upper() in upper:
            return True
    return False


def motd_matches_standing(motd: str) -> bool:
    return text_matches_standing(motd)


def is_standing_fleet(
    *,
    fleet_id: int,
    motd: str = "",
    label_texts: list[str] | None = None,
) -> tuple[bool, str]:
    """Standing is determined by MOTD / advert labels / allowlist — not by who commands the fleet."""
    if StandingFleetAllowlist.objects.filter(fleet_id=fleet_id).exists():
        return True, "allowlist"

    if motd_matches_standing(motd):
        return True, "motd"

    for label in label_texts or []:
        if text_matches_standing(label):
            return True, "fleet_label"

    return False, ""
