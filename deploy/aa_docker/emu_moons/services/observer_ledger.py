"""Corp mining observer ledger (Guns-R-Us / Rexan) for EMU Moons invoicing."""

from __future__ import annotations

import logging
import os
import re

from django.db import transaction

from emu_moons.models import EmuExtraction
from emu_moons.services.character_ledger import system_prefix
from emu_moons.services.pricing import isk_value_for_type, volume_m3_for_type

logger = logging.getLogger(__name__)

_SYSTEM_PREFIX = re.compile(r"^([A-Z0-9-]+)")
GUNS_R_US_CORP_ID = 98633922
DEFAULT_OBSERVER_CHARACTERS = ("Rexan Darkstar",)


def observer_character_names() -> tuple[str, ...]:
    raw = os.environ.get(
        "AA_EMU_MOONS_OBSERVER_CHARACTERS",
        ",".join(DEFAULT_OBSERVER_CHARACTERS),
    )
    names = tuple(n.strip() for n in raw.split(",") if n.strip())
    return names or DEFAULT_OBSERVER_CHARACTERS


def character_ledger_fallback_enabled() -> bool:
    return os.environ.get("AA_EMU_MOONS_ALLOW_CHARACTER_LEDGER", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def extraction_solar_system_key(extraction: EmuExtraction) -> str:
    """Solar system code (e.g. ``0TKF-6``), not full refinery name."""
    for candidate in (
        extraction.system_name,
        extraction.structure_name,
        extraction.moon_label,
    ):
        key = system_prefix(candidate or "")
        if key:
            return key
    return ""


def normalize_extraction_system_name(extraction: EmuExtraction) -> bool:
    key = extraction_solar_system_key(extraction)
    if not key or key == extraction.system_name:
        return False
    extraction.system_name = key[:128]
    extraction.save(update_fields=["system_name"])
    return True


def extraction_observer_ids(extraction: EmuExtraction) -> set[int]:
    """Moonmining refinery structure IDs (= miningtaxes ``observer.obs_id``)."""
    ids: set[int] = set()
    try:
        from moonmining.models import Extraction, Refinery

        if extraction.moonmining_extraction_id:
            mm = (
                Extraction.objects.filter(pk=extraction.moonmining_extraction_id)
                .select_related("refinery")
                .first()
            )
            if mm and mm.refinery_id:
                ids.add(int(mm.refinery_id))
        if not ids and extraction.structure_name:
            ref = Refinery.objects.filter(
                name__iexact=extraction.structure_name.strip()
            ).first()
            if ref:
                ids.add(int(ref.pk))
    except ImportError:
        pass
    return ids


def _resolve_user(character_id: int):
    try:
        from allianceauth.eveonline.models import EveCharacter

        ec = (
            EveCharacter.objects.filter(character_id=character_id)
            .select_related("character_ownership__user")
            .first()
        )
        if ec and hasattr(ec, "character_ownership"):
            return ec.character_ownership.user
    except Exception:
        pass
    return None


def _observer_log_queryset(extraction: EmuExtraction):
    from miningtaxes.helpers import PriceGroups
    from miningtaxes.models import AdminMiningObsLog

    start = extraction.popped_at.date()
    end = extraction.ledger_window_end.date()
    qs = AdminMiningObsLog.objects.filter(
        date__gte=start,
        date__lte=end,
        eve_type__group_id__in=PriceGroups.moon_ore_groups,
    ).select_related("observer", "eve_type", "eve_solar_system")

    observer_ids = extraction_observer_ids(extraction)
    if observer_ids:
        qs = qs.filter(observer__obs_id__in=observer_ids)
    else:
        system_key = extraction_solar_system_key(extraction)
        if system_key:
            qs = qs.filter(eve_solar_system__name__iexact=system_key)

    if extraction.moon_number:
        needle = f"moon {extraction.moon_number}".lower()
        qs = [row for row in qs if needle in (row.observer.name or "").lower()]
    else:
        qs = list(qs)
    return qs


@transaction.atomic
def sync_observer_ledger(extraction: EmuExtraction) -> int:
    """
    Build extraction ledger from Guns-R-Us corp mining observers (AdminMiningObsLog).

    Matches the moonmining refinery structure id when available; otherwise solar
    system + optional moon number on the observer name.
    """
    try:
        from miningtaxes.models import AdminMiningObsLog  # noqa: F401
    except ImportError:
        return 0

    from emu_moons.models import EmuExtractionLedgerLine

    normalize_extraction_system_name(extraction)
    rows = _observer_log_queryset(extraction)
    if not rows:
        logger.info(
            "emu_moons: no corp observer rows for extraction %s (%s); "
            "run emu_moons_sync_observers with Rexan corp mining token.",
            extraction.pk,
            extraction.moon_label,
        )
        return 0

    extraction.ledger_lines.all().delete()
    count = 0
    skipped_unlinked = 0
    for row in rows:
        char_id = int(row.miner_id)
        user = _resolve_user(char_id)
        if not user:
            skipped_unlinked += 1
            continue
        try:
            from allianceauth.eveonline.models import EveCharacter

            ec = EveCharacter.objects.filter(character_id=char_id).first()
            char_name = ec.character_name if ec else ""
        except Exception:
            char_name = ""
        qty = int(row.quantity or 0)
        if qty <= 0:
            continue
        type_id = int(row.eve_type_id)
        vol = volume_m3_for_type(type_id, qty)
        gross = isk_value_for_type(type_id, qty)
        EmuExtractionLedgerLine.objects.create(
            extraction=extraction,
            miner_character_id=char_id,
            miner_character_name=(char_name or "")[:128],
            user=user,
            type_id=type_id,
            type_name=(row.eve_type.name if row.eve_type_id else "")[:128],
            quantity=qty,
            volume_m3=vol,
            gross_isk=gross,
            observer_log_id=row.pk,
            mined_at=row.date,
        )
        count += 1
    logger.info(
        "emu_moons: observer ledger extraction %s → %s line(s) from %s log row(s)"
        "%s",
        extraction.pk,
        count,
        len(rows),
        f" ({skipped_unlinked} miner(s) not on auth)" if skipped_unlinked else "",
    )
    return count


def ensure_observer_admin_characters() -> list:
    """Register configured observer characters (default Rexan) as miningtaxes admins."""
    try:
        from allianceauth.eveonline.models import EveCharacter
        from esi.models import Token
        from miningtaxes.models import AdminCharacter
    except ImportError:
        return []

    from emu_moons.observer_scopes import required_observer_scopes

    scopes = required_observer_scopes()
    ensured = []
    for name in observer_character_names():
        ec = EveCharacter.objects.filter(character_name__iexact=name.strip()).first()
        if not ec:
            logger.warning("emu_moons: observer character %r not found on auth", name)
            continue
        if not Token.get_token(ec.character_id, scopes):
            logger.warning(
                "emu_moons: %s missing corp mining ESI scopes %s",
                ec.character_name,
                scopes,
            )
        admin, _ = AdminCharacter.objects.update_or_create(eve_character=ec)
        ensured.append(admin)
    return ensured


def sync_corp_mining_observers_sync() -> dict:
    """
    Pull AdminMiningObsLog from ESI for Guns moon invoicing.

    Tries ``AA_EMU_MOONS_OBSERVER_CHARACTERS`` first (default Rexan Darkstar),
    then other AdminCharacter rows in Guns-R-Us with a valid token.
    """
    try:
        from esi.models import Token
        from miningtaxes.models import AdminCharacter, AdminMiningObsLog
    except ImportError:
        return {"updated": 0, "log_rows": 0, "errors": ["miningtaxes not installed"]}

    before = AdminMiningObsLog.objects.count()
    errors: list[str] = []
    updated = 0
    from emu_moons.observer_scopes import required_observer_scopes

    scopes = required_observer_scopes()
    tried: set[int] = set()

    def _try_admin(admin: AdminCharacter) -> None:
        nonlocal updated
        if admin.pk in tried:
            return
        tried.add(admin.pk)
        ec = admin.eve_character
        if not Token.get_token(ec.character_id, scopes):
            return
        try:
            admin.update_mining_observers()
            updated += 1
            logger.info("emu_moons: synced corp observers via %s", ec.character_name)
        except Exception as exc:
            msg = f"{ec.character_name}: {exc}"
            errors.append(msg)
            logger.exception("emu_moons: observer sync failed for %s", ec.character_name)

    for admin in ensure_observer_admin_characters():
        _try_admin(admin)

    for admin in AdminCharacter.objects.select_related("eve_character").filter(
        eve_character__corporation_id=GUNS_R_US_CORP_ID,
    ):
        _try_admin(admin)

    after = AdminMiningObsLog.objects.count()
    return {
        "updated": updated,
        "log_rows": after,
        "new_rows": after - before,
        "errors": errors,
    }
