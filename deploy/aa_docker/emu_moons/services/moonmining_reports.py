"""Moonmining /reports Member Mining — structure profiles and ledger import."""

from __future__ import annotations

import calendar
import datetime as dt
import logging
from collections import defaultdict
from typing import Any

from django.utils import timezone

from emu_moons.models import StructureClass, StructureTaxProfile
from emu_moons.services.scheduling import _structure_class, _system_name

logger = logging.getLogger(__name__)


def infer_structure_class(refinery_name: str) -> str:
    """Classify a refinery: private only when name says so; else public/nationalized."""
    upper = (refinery_name or "").upper()
    if "NATIONALISED" in upper or "NATIONALIZED" in upper:
        return StructureClass.NATIONALIZED
    if "PRIVATE" in upper:
        return StructureClass.PRIVATE
    return StructureClass.PUBLIC


def refinery_is_tracked(refinery_id: int, refinery_name: str = "") -> bool:
    """True when this refinery should feed moonmining reports and EMU tax."""
    from emu_moons.services.moon_exclusions import refinery_is_taxable

    moon_label = ""
    try:
        from moonmining.models import Refinery

        refinery = (
            Refinery.objects.filter(pk=refinery_id)
            .select_related("moon")
            .only("name", "moon")
            .first()
        )
        if refinery and refinery.moon_id:
            moon_label = str(refinery.moon)
    except Exception:
        pass
    return refinery_is_taxable(
        refinery_id, refinery_name or "", moon_label=moon_label
    )


def sync_structure_profiles_from_refineries() -> int:
    """Ensure every moonmining refinery has a StructureTaxProfile (public by default)."""
    try:
        from moonmining.models import Refinery
    except ImportError:
        return 0

    created = 0
    for refinery in Refinery.objects.select_related("moon").iterator():
        sclass = infer_structure_class(refinery.name or "")
        prof, was_created = StructureTaxProfile.objects.get_or_create(
            moonmining_refinery_id=refinery.pk,
            defaults={
                "structure_name": refinery.name or str(refinery),
                "system_name": _system_name(refinery),
                "structure_class": sclass,
            },
        )
        if was_created:
            created += 1
            continue
        changed = False
        if not prof.structure_name:
            prof.structure_name = refinery.name or str(refinery)
            changed = True
        if not prof.system_name:
            prof.system_name = _system_name(refinery)
            changed = True
        # Do not overwrite admin-assigned private or nationalized classes.
        if prof.structure_class == StructureClass.PUBLIC and sclass != StructureClass.PUBLIC:
            if prof.private_owner_id is None:
                prof.structure_class = sclass
                changed = True
        if changed:
            prof.save()
    return created


def sync_miningtaxes_observers() -> int:
    """Refresh corp mining observer logs (AdminMiningObsLog) from ESI."""
    try:
        from miningtaxes.models import AdminCharacter
        from miningtaxes import tasks as mt_tasks
    except ImportError:
        return 0

    count = 0
    for admin in AdminCharacter.objects.select_related("eve_character").iterator():
        try:
            mt_tasks.update_admin_character.delay(character_pk=admin.pk)
            count += 1
        except Exception:
            logger.exception("Failed to queue miningtaxes update for admin %s", admin.pk)
    return count


def sync_miningtaxes_observers_sync() -> int:
    """Synchronous observer refresh (for management commands)."""
    from emu_moons.services.observer_ledger import sync_corp_mining_observers_sync

    result = sync_corp_mining_observers_sync()
    for err in result.get("errors") or []:
        logger.warning("corp observer sync: %s", err)
    return int(result.get("updated") or 0)


def sync_moonmining_member_ledgers(*, dry_run: bool = False) -> dict[str, Any]:
    """Import ESI corp mining ledger into moonmining for non-private refineries."""
    try:
        from moonmining.models import Owner, Refinery
    except ImportError:
        return {"profiles_created": 0, "refineries_synced": 0, "ledger_rows": 0, "errors": []}

    profiles_created = sync_structure_profiles_from_refineries()
    refineries_synced = 0
    ledger_rows = 0
    errors: list[str] = []

    for owner in Owner.objects.filter(is_enabled=True).select_related("corporation"):
        try:
            observer_ids = owner.fetch_mining_ledger_observers_from_esi()
        except Exception as exc:
            errors.append(f"{owner}: observers: {exc}")
            logger.exception("ESI observers failed for %s", owner)
            continue

        for refinery in owner.refineries.filter(id__in=observer_ids):
            if not refinery_is_tracked(refinery.pk, refinery.name or ""):
                continue
            if dry_run:
                refineries_synced += 1
                continue
            try:
                refinery.update_mining_ledger_from_esi()
                refineries_synced += 1
                ledger_rows += refinery.mining_ledger.count()
            except Exception as exc:
                errors.append(f"{refinery.name} ({refinery.pk}): {exc}")
                logger.exception("Ledger sync failed for refinery %s", refinery.pk)

    return {
        "profiles_created": profiles_created,
        "refineries_synced": refineries_synced,
        "ledger_rows": ledger_rows,
        "errors": errors,
    }


def tracked_refinery_ids() -> set[int]:
    """Structure IDs (moonmining Refinery PKs) that are not private."""
    try:
        from moonmining.models import Refinery
    except ImportError:
        return set()

    ids: set[int] = set()
    for refinery in Refinery.objects.only("id", "name").iterator():
        if refinery_is_tracked(refinery.pk, refinery.name or ""):
            ids.add(int(refinery.pk))
    return ids


def backfill_mining_ledger_from_miningtaxes() -> int:
    """Copy AdminMiningObsLog into moonmining MiningLedgerRecord for tracked refineries."""
    try:
        from allianceauth.authentication.models import CharacterOwnership
        from allianceauth.eveonline.models import EveCharacter
        from eveuniverse.models import EveEntity
        from miningtaxes.models import AdminMiningObsLog
        from moonmining.models import MiningLedgerRecord, Refinery
        from moonmining.models.extractions import EveOreType
    except ImportError:
        return 0

    tracked = tracked_refinery_ids()
    if not tracked:
        return 0

    refinery_by_id = {
        int(r.pk): r
        for r in Refinery.objects.filter(pk__in=tracked).only("id", "name")
    }
    char_to_user = dict(
        CharacterOwnership.objects.values_list("character__character_id", "user_id")
    )
    moon_groups = None
    try:
        from miningtaxes.helpers import PriceGroups

        moon_groups = PriceGroups.moon_ore_groups
    except ImportError:
        pass

    qs = AdminMiningObsLog.objects.select_related(
        "observer", "eve_type", "eve_type__group"
    ).filter(observer__obs_id__in=tracked)
    if moon_groups:
        qs = qs.filter(eve_type__group_id__in=moon_groups)

    written = 0
    type_ids: set[int] = set()
    rows = list(qs[:50000])
    for row in rows:
        type_ids.add(row.eve_type_id)

    EveOreType.objects.bulk_get_or_create_esi(ids=list(type_ids))

    for row in rows:
        refinery = refinery_by_id.get(int(row.observer.obs_id))
        if not refinery:
            continue
        miner_id = int(row.miner_id)
        character, _ = EveEntity.objects.get_or_create(id=miner_id)
        corp_id = 0
        try:
            ec = EveCharacter.objects.get(character_id=miner_id)
            corp_id = int(ec.corporation_id or 0)
        except EveCharacter.DoesNotExist:
            pass
        corporation, _ = EveEntity.objects.get_or_create(id=corp_id or miner_id)
        ore_type = EveOreType.objects.filter(id=row.eve_type_id).first()
        if not ore_type:
            continue
        record = MiningLedgerRecord.objects.filter(
            refinery=refinery,
            character=character,
            day=row.date,
            ore_type=ore_type,
        ).first()
        if record:
            record.quantity = int(row.quantity)
            record.user_id = char_to_user.get(miner_id)
            record.save(update_fields=["quantity", "user_id"])
        else:
            MiningLedgerRecord.objects.create(
                refinery=refinery,
                character=character,
                day=row.date,
                ore_type=ore_type,
                corporation=corporation,
                quantity=int(row.quantity),
                user_id=char_to_user.get(miner_id),
            )
            written += 1
    return written


def _refinery_by_system_name() -> dict[str, list]:
    """Map upper-case system name → tracked refineries in that system."""
    try:
        from moonmining.models import Refinery
    except ImportError:
        return {}

    by_system: dict[str, list] = defaultdict(list)
    for refinery in Refinery.objects.select_related("moon").iterator():
        if not refinery_is_tracked(refinery.pk, refinery.name or ""):
            continue
        system = (_system_name(refinery) or "").upper()
        if system:
            by_system[system].append(refinery)
    return dict(by_system)


def _report_month_starts(today: dt.date | None = None) -> list[dt.date]:
    """First day of current month and three prior months (newest first)."""
    if today is None:
        today = timezone.now().date()
    first = today.replace(day=1)
    out = [first]
    cursor = first
    for _ in range(3):
        cursor = (cursor - dt.timedelta(days=1)).replace(day=1)
        out.append(cursor)
    return out


def import_historical_member_ledger_from_characters(
    *,
    year: int | None = None,
    month: int | None = None,
    months: int = 4,
    moon_systems_only: bool = True,
) -> dict[str, Any]:
    """Build moonmining ``MiningLedgerRecord`` rows from miningtaxes character ledgers.

    Use when corp structure observer ESI is empty (common on emu) but personal
    CharacterMiningLedgerEntry rows exist (e.g. Mar–Jun 2026 in this deployment).
    """
    try:
        from allianceauth.eveonline.models import EveCharacter
        from eveuniverse.models import EveEntity
        from miningtaxes.models import CharacterMiningLedgerEntry
        from moonmining.models import MiningLedgerRecord
        from moonmining.models.extractions import EveOreType
    except ImportError:
        return {"created": 0, "updated": 0, "skipped": 0, "reason": "missing deps"}

    refinery_map = _refinery_by_system_name()
    if moon_systems_only and not refinery_map:
        return {"created": 0, "updated": 0, "skipped": 0, "reason": "no refineries"}

    if year and month:
        last_day = calendar.monthrange(year, month)[1]
        start = dt.date(year, month, 1)
        end = dt.date(year, month, last_day)
    else:
        month_starts = _report_month_starts()
        start = month_starts[-1]
        end = timezone.now().date()

    from allianceauth.authentication.models import CharacterOwnership

    char_to_user = dict(
        CharacterOwnership.objects.values_list("character__character_id", "user_id")
    )
    char_to_corp = dict(
        EveCharacter.objects.values_list("character_id", "corporation_id")
    )

    qs = (
        CharacterMiningLedgerEntry.objects.filter(date__gte=start, date__lte=end)
        .select_related("eve_type", "eve_solar_system", "character__eve_character")
        .order_by("date")
    )

    buckets: dict[tuple, dict[str, Any]] = {}
    skipped = 0
    for row in qs.iterator(chunk_size=2000):
        miner_id = int(row.character.eve_character.character_id)
        user_id = char_to_user.get(miner_id)
        if not user_id:
            skipped += 1
            continue

        system_key = (row.eve_solar_system.name or "").upper()
        if moon_systems_only:
            refineries = refinery_map.get(system_key)
            if not refineries:
                skipped += 1
                continue
            refinery = refineries[0]
        else:
            from moonmining.models import Refinery

            refinery = Refinery.objects.filter(
                pk__in=tracked_refinery_ids()
            ).first()
            if not refinery:
                skipped += 1
                continue

        key = (refinery.pk, row.date, miner_id, row.eve_type_id)
        bucket = buckets.get(key)
        if bucket is None:
            buckets[key] = {
                "refinery": refinery,
                "day": row.date,
                "miner_id": miner_id,
                "type_id": row.eve_type_id,
                "quantity": int(row.quantity or 0),
                "user_id": user_id,
                "corp_id": int(char_to_corp.get(miner_id) or 0),
            }
        else:
            bucket["quantity"] += int(row.quantity or 0)

    if not buckets:
        return {
            "created": 0,
            "updated": 0,
            "skipped": skipped,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }

    type_ids = {b["type_id"] for b in buckets.values()}
    have_types = set(EveOreType.objects.filter(id__in=type_ids).values_list("id", flat=True))
    missing_types = [tid for tid in type_ids if tid not in have_types]
    if missing_types:
        EveOreType.objects.bulk_get_or_create_esi(ids=missing_types)

    created = 0
    updated = 0
    for bucket in buckets.values():
        miner_id = bucket["miner_id"]
        character, _ = EveEntity.objects.get_or_create(id=miner_id)
        corp_id = bucket["corp_id"] or miner_id
        corporation, _ = EveEntity.objects.get_or_create(id=corp_id)
        ore_type = EveOreType.objects.filter(id=bucket["type_id"]).first()
        if not ore_type:
            skipped += 1
            continue
        record = MiningLedgerRecord.objects.filter(
            refinery=bucket["refinery"],
            character=character,
            day=bucket["day"],
            ore_type=ore_type,
        ).first()
        if record:
            record.corporation = corporation
            record.quantity = bucket["quantity"]
            record.user_id = bucket["user_id"]
            record.save(
                update_fields=["corporation", "quantity", "user_id"]
            )
            updated += 1
        else:
            MiningLedgerRecord.objects.create(
                refinery=bucket["refinery"],
                character=character,
                day=bucket["day"],
                ore_type=ore_type,
                corporation=corporation,
                quantity=bucket["quantity"],
                user_id=bucket["user_id"],
            )
            created += 1

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "bucket_count": len(buckets),
    }
