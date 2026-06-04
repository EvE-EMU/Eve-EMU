"""Attribute moon tax ledger lines from personal character mining (per ore, per miner)."""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal

from django.db import transaction

from emu_moons.models import EmuExtraction
from emu_moons.services.pricing import is_moon_ore_type_id, isk_value_for_type, volume_m3_for_type

logger = logging.getLogger(__name__)

_SYSTEM_PREFIX = re.compile(r"^([A-Z0-9-]+)")


def system_prefix(name: str) -> str:
    if not name:
        return ""
    m = _SYSTEM_PREFIX.match(name.strip().upper())
    return m.group(1) if m else name.strip().upper()


def _resolve_user_and_name(character_id: int) -> tuple[object | None, str]:
    try:
        from allianceauth.eveonline.models import EveCharacter

        ec = (
            EveCharacter.objects.filter(character_id=character_id)
            .select_related("character_ownership__user")
            .first()
        )
        if ec and hasattr(ec, "character_ownership"):
            return ec.character_ownership.user, ec.character_name or ""
    except Exception:
        pass
    return None, ""


def _esi_value(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _parse_esi_date(raw) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    if hasattr(raw, "date"):
        return raw.date()
    text = str(raw)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _miner_character_ids_in_window(
    system_key: str,
    start: date,
    end: date,
) -> set[int]:
    """Characters with any miningtaxes activity in this system during the pop window."""
    ids: set[int] = set()
    try:
        from miningtaxes.models import AdminMiningObsLog, CharacterMiningLedgerEntry

        for row in AdminMiningObsLog.objects.filter(
            date__gte=start,
            date__lte=end,
        ).select_related("eve_solar_system"):
            if system_prefix(row.eve_solar_system.name if row.eve_solar_system_id else "") == system_key:
                ids.add(int(row.miner_id))
        for row in CharacterMiningLedgerEntry.objects.filter(
            date__gte=start,
            date__lte=end,
        ).select_related("eve_solar_system", "character__eve_character"):
            if system_prefix(row.eve_solar_system.name if row.eve_solar_system_id else "") != system_key:
                continue
            ids.add(int(row.character.eve_character.character_id))
    except ImportError:
        pass
    return ids


def _accumulate_from_esi(
    buckets: dict[tuple[int, int], dict],
    *,
    system_key: str,
    start: date,
    end: date,
    character_ids: set[int] | None = None,
) -> int:
    """Pull character mining from ESI for miners active in this system (corp-only fallback)."""
    try:
        from esi.clients import EsiClientProvider
        from esi.models import Token
        from eve_sde.models import ItemType, SolarSystem
        from miningtaxes.models import Character
    except ImportError:
        return 0

    scope = "esi-industry.read_character_mining.v1"
    system_cache: dict[int, str] = {}
    type_cache: dict[int, str] = {}
    hits = 0

    if character_ids is None:
        character_ids = _miner_character_ids_in_window(system_key, start, end)
    if not character_ids:
        logger.info(
            "emu_moons: no miners in %s for %s–%s; skip ESI ledger (run miningtaxes "
            "ledger refresh or set MININGTAXES_TAX_ONLY_CORP_MOONS=0).",
            system_key,
            start,
            end,
        )
        return 0

    chars = Character.objects.filter(
        eve_character__character_id__in=character_ids,
        eve_character__character_ownership__user__isnull=False,
    ).select_related(
        "eve_character",
        "eve_character__character_ownership__user",
    )

    for mt_char in chars.iterator(chunk_size=50):
        ec = mt_char.eve_character
        cid = int(ec.character_id)
        token = Token.get_token(cid, [scope])
        if not token:
            continue
        try:
            user = ec.character_ownership.user
        except Exception:
            continue
        try:
            provider = EsiClientProvider(token=token)
            raw = provider.client.Industry.get_characters_character_id_mining(
                character_id=cid,
            )
            entries = raw if isinstance(raw, list) else list(raw or [])
        except Exception as exc:
            logger.debug("ESI mining ledger %s: %s", ec.character_name, exc)
            continue

        for entry in entries or []:
            mined = _parse_esi_date(_esi_value(entry, "date"))
            if mined is None or mined < start or mined > end:
                continue
            type_id = int(_esi_value(entry, "type_id") or 0)
            if not is_moon_ore_type_id(type_id):
                continue
            ss_id = int(_esi_value(entry, "solar_system_id") or 0)
            if ss_id not in system_cache:
                row = SolarSystem.objects.filter(id=ss_id).values_list("name", flat=True).first()
                system_cache[ss_id] = system_prefix(row or "")
            if system_cache[ss_id] != system_key:
                continue
            qty = int(_esi_value(entry, "quantity") or 0)
            if qty <= 0:
                continue
            if type_id not in type_cache:
                name = ItemType.objects.filter(id=type_id).values_list("name", flat=True).first()
                type_cache[type_id] = (name or "")[:128]
            key = (cid, type_id)
            bucket = buckets.get(key)
            if bucket is None:
                bucket = {
                    "user": user,
                    "character_name": (ec.character_name or "")[:128],
                    "type_id": type_id,
                    "type_name": type_cache[type_id],
                    "quantity": 0,
                }
                buckets[key] = bucket
            bucket["quantity"] += qty
            hits += 1
    return hits


@transaction.atomic
def sync_character_mining_ledger(extraction: EmuExtraction) -> int:
    """
  Build ledger lines from miningtaxes CharacterMiningLedgerEntry.

  One row per (miner character, ore type) in the extraction system during the pop window.
  """
    try:
        from miningtaxes.models import CharacterMiningLedgerEntry
    except ImportError:
        return 0

    from emu_moons.models import EmuExtractionLedgerLine

    system_key = system_prefix(extraction.system_name or extraction.moon_label)
    if not system_key:
        return 0

    start = extraction.popped_at.date()
    end = extraction.ledger_window_end.date()

    qs = (
        CharacterMiningLedgerEntry.objects.filter(
            date__gte=start,
            date__lte=end,
        )
        .select_related(
            "eve_solar_system",
            "eve_type",
            "character__eve_character",
            "character__eve_character__character_ownership__user",
        )
        .order_by("date", "character_id", "eve_type_id")
    )

    buckets: dict[tuple[int, int], dict] = {}

    def _accumulate(row) -> None:
        sys = system_prefix(
            row.eve_solar_system.name if row.eve_solar_system_id else ""
        )
        if sys != system_key:
            return
        type_id = int(row.eve_type_id)
        if not is_moon_ore_type_id(type_id):
            return
        ec = row.character.eve_character
        cid = int(ec.character_id)
        try:
            user = ec.character_ownership.user
        except Exception:
            return
        if not user:
            return
        key = (cid, type_id)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = {
                "user": user,
                "character_name": (ec.character_name or "")[:128],
                "type_id": type_id,
                "type_name": (row.eve_type.name if row.eve_type_id else "")[:128],
                "quantity": 0,
            }
            buckets[key] = bucket
        bucket["quantity"] += int(row.quantity or 0)

    for row in qs.iterator(chunk_size=2000):
        _accumulate(row)

    if not buckets:
        _accumulate_from_esi(
            buckets,
            system_key=system_key,
            start=start,
            end=end,
            character_ids=_miner_character_ids_in_window(system_key, start, end),
        )

    extraction.ledger_lines.all().delete()
    count = 0
    for (cid, _type_id), data in buckets.items():
        qty = int(data["quantity"])
        if qty <= 0:
            continue
        vol = volume_m3_for_type(data["type_id"], qty)
        gross = isk_value_for_type(data["type_id"], qty)
        if gross <= 0:
            gross = Decimal(qty) * Decimal("3000")
        EmuExtractionLedgerLine.objects.create(
            extraction=extraction,
            miner_character_id=cid,
            miner_character_name=data["character_name"],
            user=data["user"],
            type_id=data["type_id"],
            type_name=data["type_name"],
            quantity=qty,
            volume_m3=vol,
            gross_isk=gross,
            mined_at=start,
        )
        count += 1
    return count
