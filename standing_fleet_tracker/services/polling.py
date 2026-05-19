"""Poll ESI and update fleet sessions, locations, ships, killmails."""

from __future__ import annotations

import logging
from django.utils import timezone

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter

from standing_fleet_tracker import app_settings
from standing_fleet_tracker.models import (
    CharacterScore,
    FleetKillmail,
    FleetLocationSample,
    FleetSession,
    FleetSessionShipLog,
    ShipFleetStat,
)
from standing_fleet_tracker.services.fit_snapshots import record_fit_snapshot_for_character
from standing_fleet_tracker.services.kpi_ingest import ingest_mining_ledger, ingest_wallet_journal
from standing_fleet_tracker.services import esi as esi_api
from standing_fleet_tracker.services.sov import is_system_in_sov, sov_cache_stale
from standing_fleet_tracker.services.sov import refresh_sov_cache
from standing_fleet_tracker.services.scopes import missing_scopes_for_token, token_can_track_fleet
from standing_fleet_tracker.services.fleet_meta import resolve_fleet_metadata
from standing_fleet_tracker.services.pulse import record_fleet_pulse
from standing_fleet_tracker.services.standing_detect import is_standing_fleet

logger = logging.getLogger(__name__)


def iter_tracked_characters():
    """Characters with ownership and a usable fleet scope token."""
    char_ids = (
        CharacterOwnership.objects.filter(user__is_active=True)
        .values_list("character_id", flat=True)
        .distinct()
    )
    for char_id in char_ids:
        try:
            character = EveCharacter.objects.get(pk=char_id)
        except EveCharacter.DoesNotExist:
            continue
        token = esi_api.token_for_character(character.character_id)
        if not token_can_track_fleet(token):
            missing = missing_scopes_for_token(token)
            if missing:
                logger.debug(
                    "SFT skip %s: missing scopes %s",
                    character.character_name,
                    ", ".join(missing),
                )
            continue
        yield character, token


def _open_session(
    character,
    fleet_id: int,
    token,
    *,
    fleet_boss_id: int | None = None,
) -> FleetSession:
    meta = resolve_fleet_metadata(fleet_id, token, fleet_boss_id=fleet_boss_id)
    standing, classification = is_standing_fleet(
        fleet_id=fleet_id,
        motd=meta["motd"],
        label_texts=meta["labels"],
    )
    return FleetSession.objects.create(
        character=character,
        fleet_id=fleet_id,
        is_standing_fleet=standing,
        classification=classification,
        fleet_commander_id=meta["fleet_commander_id"],
        motd_snapshot=str(meta["motd"])[:2000],
        fleet_label_snapshot=str(meta["label_snapshot"])[:255],
    )


def _close_session(session: FleetSession) -> None:
    if session.ended_at:
        return
    session.ended_at = timezone.now()
    session.save(update_fields=["ended_at"])


def _refresh_active_session(
    session: FleetSession,
    fleet_id: int,
    token,
    *,
    fleet_boss_id: int | None = None,
) -> None:
    """Re-check MOTD / advert labels / allowlist while still in the same fleet."""
    boss_id = fleet_boss_id or session.fleet_commander_id
    meta = resolve_fleet_metadata(fleet_id, token, fleet_boss_id=boss_id)
    standing, classification = is_standing_fleet(
        fleet_id=fleet_id,
        motd=meta["motd"],
        label_texts=meta["labels"],
    )
    motd = str(meta["motd"])[:2000]
    label = str(meta["label_snapshot"])[:255]
    commander_id = meta["fleet_commander_id"]
    updates: list[str] = []
    if session.is_standing_fleet != standing:
        session.is_standing_fleet = standing
        updates.append("is_standing_fleet")
    if session.classification != classification:
        session.classification = classification
        updates.append("classification")
    if session.motd_snapshot != motd:
        session.motd_snapshot = motd
        updates.append("motd_snapshot")
    if session.fleet_label_snapshot != label:
        session.fleet_label_snapshot = label
        updates.append("fleet_label_snapshot")
    if commander_id and session.fleet_commander_id != commander_id:
        session.fleet_commander_id = commander_id
        updates.append("fleet_commander_id")
    if updates:
        session.save(update_fields=updates)


def poll_user_characters(user) -> dict:
    """Poll only characters owned by this AA user (for dashboard refresh)."""
    char_ids = CharacterOwnership.objects.filter(user=user).values_list(
        "character_id", flat=True
    )
    polled = 0
    errors = 0
    for char_id in char_ids:
        try:
            character = EveCharacter.objects.get(pk=char_id)
        except EveCharacter.DoesNotExist:
            continue
        token = esi_api.token_for_character(character.character_id)
        if not token_can_track_fleet(token):
            continue
        try:
            poll_character(character, token)
            polled += 1
        except Exception:
            logger.exception("SFT poll failed for %s", character)
            errors += 1
    return {"polled": polled, "errors": errors}


def _record_location(
    character,
    session: FleetSession | None,
    solar_system_id: int,
    in_standing: bool,
) -> FleetLocationSample | None:
    in_sov = is_system_in_sov(solar_system_id)
    prev = (
        FleetLocationSample.objects.filter(character=character)
        .order_by("-recorded_at")
        .first()
    )
    sample = FleetLocationSample.objects.create(
        session=session,
        character=character,
        solar_system_id=solar_system_id,
        in_standing_fleet=in_standing,
        in_sov_space=in_sov,
    )
    return sample


def _record_ship_log(session: FleetSession, ship_type_id: int, ship_name: str) -> None:
    last = (
        FleetSessionShipLog.objects.filter(session=session)
        .order_by("-recorded_at")
        .first()
    )
    if (
        last
        and last.ship_type_id == ship_type_id
        and (last.ship_name or "") == (ship_name or "")
    ):
        return
    FleetSessionShipLog.objects.create(
        session=session,
        ship_type_id=ship_type_id,
        ship_name=ship_name or "",
    )


def _update_ship_stats(character, ship_type_id: int, ship_name: str, seconds: int) -> None:
    stat, _ = ShipFleetStat.objects.get_or_create(
        character=character,
        ship_type_id=ship_type_id,
        defaults={"ship_name": ship_name or ""},
    )
    stat.seconds_flown += max(seconds, 0)
    stat.session_count += 0
    if ship_name and not stat.ship_name:
        stat.ship_name = ship_name
    stat.save(update_fields=["seconds_flown", "ship_name"])


def _process_killmails(character, token, session: FleetSession | None) -> None:
    status, recent = esi_api.get_character_killmails(character.character_id, token)
    if status != 200 or not recent:
        return

    for entry in recent[:10]:
        km_id = int(entry["killmail_id"])
        if FleetKillmail.objects.filter(killmail_id=km_id).exists():
            continue
        km_hash = entry["killmail_hash"]
        kstatus, km = esi_api.get_killmail(km_id, km_hash, token)
        if kstatus != 200 or not km:
            continue

        system_id = km.get("solar_system_id")
        victim = (km.get("victim") or {})
        victim_char = victim.get("character_id")
        victim_alliance = victim.get("alliance_id")
        from django.utils.dateparse import parse_datetime

        killed_at = parse_datetime(str(km.get("killmail_time", ""))) or timezone.now()

        home_defence = False
        if system_id and is_system_in_sov(int(system_id)):
            if victim_alliance and int(victim_alliance) != app_settings.SFT_ALLIANCE_ID:
                home_defence = True

        attacker_ids = {
            a.get("character_id")
            for a in km.get("attackers", [])
            if a.get("character_id")
        }
        if character.character_id not in attacker_ids:
            continue

        FleetKillmail.objects.create(
            character=character,
            session=session,
            killmail_id=km_id,
            killmail_hash=km_hash,
            solar_system_id=system_id,
            ship_type_id=victim.get("ship_type_id"),
            victim_character_id=victim_char,
            is_home_defence=home_defence,
            killed_at=killed_at,
        )


def poll_character(character: EveCharacter, token) -> None:
    now = timezone.now()
    char_id = character.character_id

    status, fleet = esi_api.get_character_fleet(char_id, token)
    active = (
        FleetSession.objects.filter(character=character, ended_at__isnull=True)
        .order_by("-started_at")
        .first()
    )

    if status == 404:
        if active:
            _close_session(active)
        CharacterScore.objects.update_or_create(character=character, defaults={"last_polled_at": now})
        return

    if status != 200 or not fleet:
        return

    fleet_id = int(fleet["fleet_id"])
    fleet_boss_id = fleet.get("fleet_boss_id")
    if fleet_boss_id is not None:
        fleet_boss_id = int(fleet_boss_id)
    if not active or active.fleet_id != fleet_id:
        if active:
            _close_session(active)
        active = _open_session(character, fleet_id, token, fleet_boss_id=fleet_boss_id)
    else:
        _refresh_active_session(active, fleet_id, token, fleet_boss_id=fleet_boss_id)

    loc_status, loc = esi_api.get_character_location(char_id, token)
    if loc_status == 200 and loc:
        sid = int(loc["solar_system_id"])
        _record_location(character, active, sid, active.is_standing_fleet)

    ship_status, ship = esi_api.get_character_ship(char_id, token)
    if ship_status == 200 and ship:
        stid = int(ship["ship_type_id"])
        sname = str(ship.get("ship_name") or "")
        if active.last_ship_type_id != stid:
            poll_seconds = app_settings.SFT_POLL_INTERVAL_SECONDS
            _update_ship_stats(character, stid, sname, poll_seconds)
        active.last_ship_type_id = stid
        active.last_ship_name = sname
        active.save(update_fields=["last_ship_type_id", "last_ship_name"])
        _record_ship_log(active, stid, sname)
        record_fit_snapshot_for_character(
            character,
            token,
            active,
            in_standing_fleet=active.is_standing_fleet,
        )

    _process_killmails(character, token, active)
    try:
        ingest_wallet_journal(character, token)
        ingest_mining_ledger(character, token)
    except Exception:
        logger.exception("SFT KPI ingest failed for %s", character)
    record_fleet_pulse(
        fleet_id=fleet_id,
        token=token,
        fleet_boss_id=fleet_boss_id,
        polled_by=character,
        is_standing_fleet=active.is_standing_fleet,
    )
    CharacterScore.objects.update_or_create(character=character, defaults={"last_polled_at": now})


def poll_all_characters() -> dict:
    if sov_cache_stale():
        refresh_sov_cache()

    polled = 0
    errors = 0
    limit = max(app_settings.SFT_MAX_CHARACTERS_PER_POLL, 0)
    for character, token in iter_tracked_characters():
        if limit and polled + errors >= limit:
            break
        try:
            poll_character(character, token)
            polled += 1
        except Exception:
            logger.exception("SFT poll failed for %s", character)
            errors += 1
    return {"polled": polled, "errors": errors, "limit": limit or None}
