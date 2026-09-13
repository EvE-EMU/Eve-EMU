"""ESI scope constants for EMUMS character audit (no config imports)."""

from __future__ import annotations

# CorpTools-style character audit scope set — register all on the EMUMS CCP application.
CHARACTER_AUDIT_SCOPES: tuple[str, ...] = (
    "publicData",
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-wallet.read_character_wallet.v1",
    "esi-assets.read_assets.v1",
    "esi-assets.read_corporation_assets.v1",
    "esi-markets.structure_markets.v1",
    "esi-markets.read_character_orders.v1",
    "esi-location.read_location.v1",
    "esi-location.read_online.v1",
    "esi-location.read_ship_type.v1",
    "esi-characters.read_fatigue.v1",
    "esi-universe.read_structures.v1",
    "esi-search.search_structures.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-contracts.read_character_contracts.v1",
    "esi-characters.read_corporation_roles.v1",
    "esi-characters.read_titles.v1",
    "esi-characters.read_standings.v1",
    "esi-characters.read_contacts.v1",
    "esi-characters.read_notifications.v1",
    "esi-killmails.read_killmails.v1",
    "esi-fittings.read_fittings.v1",
    "esi-characters.read_blueprints.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-industry.read_character_mining.v1",
    "esi-characters.read_loyalty.v1",
    "esi-calendar.read_calendar_events.v1",
    "esi-mail.read_mail.v1",
    "esi-planets.manage_planets.v1",
)

DEFAULT_SSO_SCOPES_STRING = " ".join(CHARACTER_AUDIT_SCOPES)
