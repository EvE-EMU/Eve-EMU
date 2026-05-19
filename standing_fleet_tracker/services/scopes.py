"""ESI scope checks for standing fleet tracking."""

from __future__ import annotations

from esi.models import Token

from standing_fleet_tracker import app_settings


def required_scopes() -> list[str]:
    return [s.strip() for s in app_settings.SFT_REQUIRED_SCOPES if s.strip()]


def missing_scopes_for_token(token: Token | None) -> list[str]:
    required = required_scopes()
    if not token:
        return required
    have = set(token.scopes.values_list("name", flat=True))
    return [scope for scope in required if scope not in have]


def token_can_track_fleet(token: Token | None) -> bool:
    return not missing_scopes_for_token(token)
