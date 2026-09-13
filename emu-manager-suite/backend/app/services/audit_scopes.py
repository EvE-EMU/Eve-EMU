"""Character sheet ESI scope requirements and grant status."""

from __future__ import annotations

import json
from typing import Any

from app.config import settings

from app.audit_scope_constants import CHARACTER_AUDIT_SCOPES, DEFAULT_SSO_SCOPES_STRING
SCOPE_LABELS: dict[str, str] = {
    "publicData": "Public character data",
    "esi-skills.read_skills.v1": "Skills & skill points",
    "esi-skills.read_skillqueue.v1": "Skill training queue",
    "esi-wallet.read_character_wallet.v1": "Wallet balance & journal",
    "esi-assets.read_assets.v1": "Hangar & ship assets",
    "esi-assets.read_corporation_assets.v1": "Corporation hangar assets",
    "esi-markets.structure_markets.v1": "Structure markets",
    "esi-markets.read_character_orders.v1": "Character market orders",
    "esi-location.read_location.v1": "Current location",
    "esi-location.read_online.v1": "Online status",
    "esi-location.read_ship_type.v1": "Active ship",
    "esi-characters.read_fatigue.v1": "Jump fatigue",
    "esi-universe.read_structures.v1": "Structure details",
    "esi-search.search_structures.v1": "Structure search",
    "esi-clones.read_clones.v1": "Jump clones",
    "esi-clones.read_implants.v1": "Active implants",
    "esi-contracts.read_character_contracts.v1": "Character contracts",
    "esi-characters.read_corporation_roles.v1": "Corporation roles",
    "esi-characters.read_titles.v1": "Corporation titles",
    "esi-characters.read_standings.v1": "NPC standings",
    "esi-characters.read_contacts.v1": "Contacts",
    "esi-characters.read_notifications.v1": "Notifications",
    "esi-killmails.read_killmails.v1": "Killmails",
    "esi-fittings.read_fittings.v1": "Ship fittings",
    "esi-characters.read_blueprints.v1": "Blueprint library",
    "esi-industry.read_character_jobs.v1": "Industry jobs",
    "esi-industry.read_character_mining.v1": "Mining ledger",
    "esi-characters.read_loyalty.v1": "Loyalty points",
    "esi-calendar.read_calendar_events.v1": "Calendar events",
    "esi-mail.read_mail.v1": "Mail",
    "esi-planets.manage_planets.v1": "Planetary interaction colonies",
}

WALLET_SCOPES = frozenset({"esi-wallet.read_character_wallet.v1"})
ASSETS_SCOPES = frozenset({"esi-assets.read_assets.v1"})
CORP_ASSETS_SCOPES = frozenset({"esi-assets.read_corporation_assets.v1"})
SKILLS_SCOPES = frozenset({"esi-skills.read_skills.v1"})
SKILL_QUEUE_SCOPES = frozenset({"esi-skills.read_skillqueue.v1"})
LOCATION_SCOPES = frozenset({"esi-location.read_location.v1"})
CLONES_SCOPES = frozenset({"esi-clones.read_clones.v1", "esi-clones.read_implants.v1"})
CONTRACTS_SCOPES = frozenset({"esi-contracts.read_character_contracts.v1"})
MAIL_SCOPES = frozenset({"esi-mail.read_mail.v1"})
KILLMAIL_SCOPES = frozenset({"esi-killmails.read_killmails.v1"})
PI_SCOPES = frozenset({"esi-planets.manage_planets.v1"})
FITTINGS_SCOPES = frozenset({"esi-fittings.read_fittings.v1"})
BLUEPRINTS_SCOPES = frozenset({"esi-characters.read_blueprints.v1"})
ONLINE_SCOPES = frozenset({"esi-location.read_online.v1"})
SHIP_TYPE_SCOPES = frozenset({"esi-location.read_ship_type.v1"})
FATIGUE_SCOPES = frozenset({"esi-characters.read_fatigue.v1"})
STRUCTURE_MARKETS_SCOPES = frozenset({"esi-markets.structure_markets.v1"})
CHARACTER_ORDERS_SCOPES = frozenset({"esi-markets.read_character_orders.v1"})
STRUCTURES_READ_SCOPES = frozenset({"esi-universe.read_structures.v1"})
SEARCH_STRUCTURES_SCOPES = frozenset({"esi-search.search_structures.v1"})
CORP_ROLES_SCOPES = frozenset({"esi-characters.read_corporation_roles.v1"})
STANDINGS_SCOPES = frozenset({"esi-characters.read_standings.v1"})
CONTACTS_SCOPES = frozenset({"esi-characters.read_contacts.v1"})
NOTIFICATIONS_SCOPES = frozenset({"esi-characters.read_notifications.v1"})
INDUSTRY_JOBS_SCOPES = frozenset({"esi-industry.read_character_jobs.v1"})
MINING_SCOPES = frozenset({"esi-industry.read_character_mining.v1"})
LOYALTY_SCOPES = frozenset({"esi-characters.read_loyalty.v1"})
CALENDAR_SCOPES = frozenset({"esi-calendar.read_calendar_events.v1"})


def configured_scopes() -> list[str]:
    raw = (settings.sso_scopes or "").strip()
    if not raw:
        return list(CHARACTER_AUDIT_SCOPES)
    return [part.strip() for part in raw.split() if part.strip()]


def parse_granted_scopes(raw: Any) -> set[str]:
    if raw is None:
        return set()
    if isinstance(raw, list):
        return {str(s).strip() for s in raw if str(s).strip()}
    text = str(raw).strip()
    if not text:
        return set()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return {str(s).strip() for s in parsed if str(s).strip()}
    except (TypeError, json.JSONDecodeError):
        pass
    return {part.strip() for part in text.replace(",", " ").split() if part.strip()}


def missing_scopes(granted: set[str]) -> list[str]:
    return [scope for scope in configured_scopes() if scope not in granted]


def scope_status(granted: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scope in configured_scopes():
        rows.append(
            {
                "scope": scope,
                "label": SCOPE_LABELS.get(scope, scope),
                "granted": scope in granted,
            }
        )
    return rows


def has_wallet_access(granted: set[str]) -> bool:
    return bool(WALLET_SCOPES & granted)


def has_assets_access(granted: set[str]) -> bool:
    return bool(ASSETS_SCOPES & granted)


def has_corp_assets_access(granted: set[str]) -> bool:
    return bool(CORP_ASSETS_SCOPES & granted)


def has_skills_access(granted: set[str]) -> bool:
    return bool(SKILLS_SCOPES & granted)


def has_skill_queue_access(granted: set[str]) -> bool:
    return bool(SKILL_QUEUE_SCOPES & granted)


def has_location_access(granted: set[str]) -> bool:
    return bool(LOCATION_SCOPES & granted)


def has_clones_access(granted: set[str]) -> bool:
    return bool({"esi-clones.read_clones.v1", "esi-clones.read_implants.v1"} & granted)


def has_contracts_access(granted: set[str]) -> bool:
    return bool(CONTRACTS_SCOPES & granted)


def has_mail_access(granted: set[str]) -> bool:
    return bool(MAIL_SCOPES & granted)


def has_killmails_access(granted: set[str]) -> bool:
    return bool(KILLMAIL_SCOPES & granted)


def has_pi_access(granted: set[str]) -> bool:
    return bool(PI_SCOPES & granted)


def has_fittings_access(granted: set[str]) -> bool:
    return bool(FITTINGS_SCOPES & granted)


def has_blueprints_access(granted: set[str]) -> bool:
    return bool(BLUEPRINTS_SCOPES & granted)


def has_online_access(granted: set[str]) -> bool:
    return bool(ONLINE_SCOPES & granted)


def has_ship_type_access(granted: set[str]) -> bool:
    return bool(SHIP_TYPE_SCOPES & granted)


def has_fatigue_access(granted: set[str]) -> bool:
    return bool(FATIGUE_SCOPES & granted)


def has_structure_markets_access(granted: set[str]) -> bool:
    return bool(STRUCTURE_MARKETS_SCOPES & granted)


def has_character_orders_access(granted: set[str]) -> bool:
    return bool(CHARACTER_ORDERS_SCOPES & granted)


def has_structures_read_access(granted: set[str]) -> bool:
    return bool(STRUCTURES_READ_SCOPES & granted)


def has_search_structures_access(granted: set[str]) -> bool:
    return bool(SEARCH_STRUCTURES_SCOPES & granted)


def has_corp_roles_access(granted: set[str]) -> bool:
    return bool(CORP_ROLES_SCOPES & granted)


def has_standings_access(granted: set[str]) -> bool:
    return bool(STANDINGS_SCOPES & granted)


def has_contacts_access(granted: set[str]) -> bool:
    return bool(CONTACTS_SCOPES & granted)


def has_notifications_access(granted: set[str]) -> bool:
    return bool(NOTIFICATIONS_SCOPES & granted)


def has_industry_jobs_access(granted: set[str]) -> bool:
    return bool(INDUSTRY_JOBS_SCOPES & granted)


def has_mining_access(granted: set[str]) -> bool:
    return bool(MINING_SCOPES & granted)


def has_loyalty_access(granted: set[str]) -> bool:
    return bool(LOYALTY_SCOPES & granted)


def has_calendar_access(granted: set[str]) -> bool:
    return bool(CALENDAR_SCOPES & granted)
