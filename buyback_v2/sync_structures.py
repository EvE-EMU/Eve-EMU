"""Sync ESI structure lists into aa-buybackprogram Location rows."""

from __future__ import annotations

import logging
import os
from typing import Any

import requests
from buybackprogram.models import Location, Owner, Program
from buybackprogram.providers import esi
from buybackprogram_esi_compat import esi_row_to_dict
from django.conf import settings
from esi.exceptions import HTTPClientError
from esi.models import Token
from eveuniverse.models import EveSolarSystem

logger = logging.getLogger(__name__)

GUNS_R_US_CORP_ID = 98633922
CORP_STRUCTURES_SCOPE = "esi-corporations.read_structures.v1"
UNIVERSE_STRUCTURES_SCOPE = "esi-universe.read_structures.v1"
DEFAULT_CHARACTER_NAME = "sevey"


def _truncate_location_name(name: str) -> str:
    name = (name or "Structure").strip()
    if len(name) <= 32:
        return name
    return name[:29] + "..."


def _resolve_solar_system(system_id: int) -> EveSolarSystem | None:
    solar = EveSolarSystem.objects.filter(pk=system_id).first()
    if solar:
        return solar
    if hasattr(EveSolarSystem.objects, "get_or_create_esi"):
        solar, _ = EveSolarSystem.objects.get_or_create_esi(id=system_id)
        return solar
    logger.warning("buyback sync: solar system %s missing from SDE", system_id)
    return None


def _token_for_corp(corp_id: int) -> Token | None:
    try:
        from structures_corp_token import structures_token_overrides
    except ImportError:
        structures_token_overrides = None  # type: ignore[assignment]

    token_pk = None
    if structures_token_overrides is not None:
        token_pk = structures_token_overrides().get(int(corp_id))

    if token_pk is not None:
        qs = Token.objects.filter(pk=token_pk)
        token = qs.require_scopes(CORP_STRUCTURES_SCOPE).first()
        if token:
            return token
        token = qs.first()
        if token:
            logger.warning(
                "buyback sync: using token pk=%s without %s in django-esi scopes",
                token_pk,
                CORP_STRUCTURES_SCOPE,
            )
            return token

    try:
        from allianceauth.eveonline.models import EveCharacter
    except ImportError:
        return None

    char_ids = EveCharacter.objects.filter(corporation_id=corp_id).values_list(
        "character_id", flat=True
    )
    return (
        Token.objects.filter(character_id__in=char_ids)
        .require_scopes(CORP_STRUCTURES_SCOPE)
        .order_by("-created")
        .first()
    )


def fetch_corporation_structures(corp_id: int, token: Token) -> list[dict[str, Any]]:
    rows = esi.client.Corporation.GetCorporationsCorporationIdStructures(
        corporation_id=corp_id,
        token=token,
    ).results(use_etag=False)
    return [esi_row_to_dict(row) for row in rows]


def _token_for_character_name(character_name: str, scope: str):
    try:
        from allianceauth.eveonline.models import EveCharacter
    except ImportError:
        return None

    ec = EveCharacter.objects.filter(character_name__iexact=character_name.strip()).first()
    if not ec:
        return None

    token = (
        Token.objects.filter(character_id=ec.character_id)
        .require_scopes(scope)
        .order_by("-created")
        .first()
    )
    if not token:
        token = (
            Token.objects.filter(character_id=ec.character_id)
            .order_by("-created")
            .first()
        )
    if not token:
        return None
    return ec, token


def _try_fetch_character_structures_endpoint(character_id: int, token: Token) -> list[dict[str, Any]]:
    """Custom or future ESI route: GET /characters/{character_id}/structures/."""
    base = os.environ.get("ESI_API_URL", getattr(settings, "ESI_API_URL", "https://esi.evetech.net/"))
    base = str(base).rstrip("/")
    if not base.endswith("/latest"):
        base = f"{base}/latest"
    url = f"{base}/characters/{character_id}/structures/"
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token.valid_access_token()}"},
            timeout=30,
        )
    except requests.RequestException:
        return []
    if response.status_code == 404:
        return []
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            rows.append(item)
        else:
            rows.append(esi_row_to_dict(item))
    return rows


def _structure_row_from_universe(structure_id: int, info: dict[str, Any]) -> dict[str, Any]:
    system_id = info.get("solar_system_id") or info.get("system_id")
    return {
        "structure_id": structure_id,
        "name": info.get("name") or str(structure_id),
        "system_id": system_id,
    }


def fetch_dockable_public_structures(token: Token) -> list[dict[str, Any]]:
    """Probe GET /universe/structures/ IDs with the character token (200 = can dock)."""
    structure_ids = esi.client.Universe.GetUniverseStructures().results(use_etag=False)
    rows: list[dict[str, Any]] = []
    for index, structure_id in enumerate(structure_ids, start=1):
        try:
            info = esi.client.Universe.GetUniverseStructuresStructureId(
                structure_id=structure_id,
                token=token,
            ).result(use_etag=False)
            rows.append(_structure_row_from_universe(int(structure_id), esi_row_to_dict(info)))
        except HTTPClientError as exc:
            if getattr(exc, "status_code", None) == 403:
                continue
            logger.warning("buyback sync: universe structure %s: %s", structure_id, exc)
        if index % 100 == 0:
            logger.info("buyback sync: probed %s/%s public structures", index, len(structure_ids))
    return rows


def fetch_structures_via_character_search(
    character_id: int, token: Token, system_names: list[str]
) -> list[dict[str, Any]]:
    """Discover structure IDs via GET /characters/{id}/search?categories=structure."""
    seen: set[int] = set()
    rows: list[dict[str, Any]] = []
    for system_name in system_names:
        if not system_name:
            continue
        try:
            result = esi.client.Search.GetCharactersCharacterIdSearch(
                character_id=character_id,
                search=system_name,
                categories=["structure"],
                token=token,
            ).result(use_etag=False)
        except Exception as exc:
            logger.warning("buyback sync: search %r failed: %s", system_name, exc)
            continue
        data = esi_row_to_dict(result)
        for structure_id in data.get("structure") or []:
            structure_id = int(structure_id)
            if structure_id in seen:
                continue
            seen.add(structure_id)
            try:
                info = esi.client.Universe.GetUniverseStructuresStructureId(
                    structure_id=structure_id,
                    token=token,
                ).result(use_etag=False)
            except HTTPClientError:
                continue
            rows.append(_structure_row_from_universe(structure_id, esi_row_to_dict(info)))
    return rows


def fetch_character_dockable_structures(character_name: str) -> list[dict[str, Any]]:
    """
    Structures the character can dock at (no single official ESI list on Tranquility).

    Uses, in order: optional GET /characters/{id}/structures/, public-universe probe,
    and per-system character search for systems already used as buyback locations.
    """
    resolved = _token_for_character_name(character_name, UNIVERSE_STRUCTURES_SCOPE)
    if not resolved:
        raise RuntimeError(f"Character {character_name!r} or ESI token not found.")
    character, token = resolved

    by_id: dict[int, dict[str, Any]] = {}

    def merge(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            sid = row.get("structure_id")
            if sid:
                by_id[int(sid)] = row

    merge(_try_fetch_character_structures_endpoint(character.character_id, token))
    merge(fetch_dockable_public_structures(token))

    system_names = list(
        Location.objects.exclude(structure_id__isnull=True)
        .exclude(eve_solar_system__isnull=True)
        .values_list("eve_solar_system__name", flat=True)
        .distinct()
    )
    if system_names:
        merge(
            fetch_structures_via_character_search(
                character.character_id, token, system_names
            )
        )

    return list(by_id.values())


def _upsert_structure_rows(
    structures: list[dict[str, Any]],
    *,
    buyback_owner: Owner | None,
    dry_run: bool,
) -> tuple[dict[str, int], list[int]]:
    stats = {"created": 0, "updated": 0, "skipped": 0, "attached_links": 0}
    location_pks: list[int] = []

    if buyback_owner is None:
        buyback_owner = Owner.objects.order_by("pk").first()

    for row in structures:
        structure_id = row.get("structure_id")
        system_id = row.get("system_id")
        if not structure_id or not system_id:
            stats["skipped"] += 1
            continue

        solar = _resolve_solar_system(int(system_id))
        if solar is None:
            stats["skipped"] += 1
            continue

        name = _truncate_location_name(str(row.get("name") or structure_id))
        defaults = {
            "name": name,
            "eve_solar_system": solar,
            "owner": buyback_owner,
        }

        if dry_run:
            if Location.objects.filter(structure_id=structure_id).exists():
                stats["updated"] += 1
            else:
                stats["created"] += 1
            continue

        location, created = Location.objects.update_or_create(
            structure_id=structure_id,
            defaults=defaults,
        )
        if created:
            stats["created"] += 1
        else:
            stats["updated"] += 1
        location_pks.append(location.pk)

    return stats, location_pks


def _attach_locations_to_programs(
    location_pks: list[int],
    *,
    program_ids: list[int] | None,
    stats: dict[str, int],
) -> None:
    programs = Program.objects.all()
    if program_ids:
        programs = programs.filter(pk__in=program_ids)
    locations = Location.objects.filter(pk__in=location_pks)
    for program in programs:
        before = program.location.count()
        program.location.add(*locations)
        after = program.location.count()
        stats["attached_links"] += max(0, after - before)


def sync_character_structures_to_buyback(
    *,
    character_name: str = DEFAULT_CHARACTER_NAME,
    buyback_owner: Owner | None = None,
    attach_programs: bool = True,
    program_ids: list[int] | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    structures = fetch_character_dockable_structures(character_name)
    stats, location_pks = _upsert_structure_rows(
        structures, buyback_owner=buyback_owner, dry_run=dry_run
    )
    if dry_run or not attach_programs:
        return stats
    _attach_locations_to_programs(location_pks, program_ids=program_ids, stats=stats)
    return stats


def sync_corp_structures_to_buyback(
    *,
    corporation_id: int = GUNS_R_US_CORP_ID,
    buyback_owner: Owner | None = None,
    attach_programs: bool = True,
    program_ids: list[int] | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """
    Import GET /corporations/{id}/structures/ into buybackprogram.Location.

    Returns counts: created, updated, skipped, attached_links.
    """
    token = _token_for_corp(corporation_id)
    if not token:
        raise RuntimeError(
            f"No ESI token with {CORP_STRUCTURES_SCOPE} for corporation {corporation_id}. "
            "Set AA_GUNS_R_US_CORP_TOKEN_ID or AA_STRUCTURES_AUTH_CHARACTER (Rexan Darkstar)."
        )

    structures = fetch_corporation_structures(corporation_id, token)
    stats, location_pks = _upsert_structure_rows(
        structures, buyback_owner=buyback_owner, dry_run=dry_run
    )
    if dry_run or not attach_programs:
        return stats
    _attach_locations_to_programs(location_pks, program_ids=program_ids, stats=stats)
    return stats
