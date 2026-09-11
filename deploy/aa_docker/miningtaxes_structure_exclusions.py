"""Corp-moon tax rules for aa-miningtaxes.

No moon taxes before 2026-08-08. From 2026-08-08, listed structures are
ignored for everyone (blanket exemption -- see 2026-09-11 update below).

Stock miningtaxes only has system whitelist/blacklist. Corp-moon taxes are
merged from ``AdminMiningObsLog`` (observer = structure id).

2026-09-11: corrected per a live audit against AdminMiningObsLog (real
observer IDs, not guessed) —
  - MOON_TAX_START_DATE moved 2026-08-04 -> 2026-08-08 (the actual date
    taxes started) and EFFECTIVE_DATE collapsed onto the same date (the
    5-day gap was a one-time rollout artifact, not an ongoing policy).
  - Added 1053322615480 (U-TJ7Y - F4LSE IX 17 - SEVEY) to the exemption --
    it had 62 rows of real observer data and was missing entirely, so it
    was being taxed for everyone including Sevey himself.
  - The 3 "SEV"/"SEVEY" structures were initially treated as exempt only
    for Sevey's own characters (SEVEY_OWNED_STRUCTURE_IDS), since the
    original report used the same "SEV"/"SEVEY" shorthand as the other
    blanket-exempt structures without an obvious "conditional" signal.
    Confirmed wrong later the same day: character Darksend (not a Sevey
    alt) got taxed for mining 9CK-KZ - F4L5E VIII 1 - SEV, which the user
    said should not happen. All 3 moved to the blanket IGNORE_ALL list.
    SEVEY_OWNED_STRUCTURE_IDS/resolve_sevey_miner_ids() kept (now unused
    unless a future structure needs a Sevey-only exemption again).
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from typing import Any, Iterable

logger = logging.getLogger(__name__)

MOON_TAX_START_DATE = dt.date(2026, 8, 8)
EFFECTIVE_DATE = dt.date(2026, 8, 8)

# Always ignore from EFFECTIVE_DATE (every miner).
IGNORE_ALL_STRUCTURE_IDS: frozenset[int] = frozenset(
    {
        1054795721754,  # WUZ-WM - F4L5E VI 13 - DIRECTOR
        1054795904753,  # GY5-26 - F4L5E XII 6 - PFC
        1055308985174,  # U-TJ7Y - VII-3 PRIVATE
        1054795665203,  # 4N-BUI - F4L5E X 20 - MIKEY
        1054795569320,  # GY5-26 - F4L5E XI - 16 - SEV
        1051756288325,  # 9CK-KZ - F4L5E VIII 1 - SEV
        1053322615480,  # U-TJ7Y - F4LSE IX 17 - SEVEY
    }
)

# Ignore from EFFECTIVE_DATE only when the miner is Sevey. Currently empty --
# the 3 SEV/SEVEY structures moved to the blanket list above 2026-09-11.
# Kept in case a future structure needs a Sevey-only (not blanket) exemption.
SEVEY_OWNED_STRUCTURE_IDS: frozenset[int] = frozenset()

SEVEY_MAIN_CHARACTER_ID = 715529239
SEVEY_USERNAMES = frozenset({"sevey"})

_sevey_miner_ids_cache: frozenset[int] | None = None


def _parse_int_set(raw: str) -> set[int]:
    out: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            continue
    return out


def _parse_date(raw: str) -> dt.date | None:
    text = (raw or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def moon_tax_start_date() -> dt.date:
    parsed = _parse_date(os.environ.get("AA_MININGTAXES_MOON_TAX_START_DATE", ""))
    return parsed or MOON_TAX_START_DATE


def effective_date() -> dt.date:
    parsed = _parse_date(os.environ.get("AA_MININGTAXES_STRUCTURE_EXCLUSION_DATE", ""))
    return parsed or EFFECTIVE_DATE


def ignore_all_structure_ids() -> frozenset[int]:
    extra = _parse_int_set(os.environ.get("AA_MININGTAXES_IGNORE_STRUCTURE_IDS", ""))
    return frozenset(IGNORE_ALL_STRUCTURE_IDS | extra)


def sevey_owned_structure_ids() -> frozenset[int]:
    extra = _parse_int_set(
        os.environ.get("AA_MININGTAXES_SEVEY_OWNED_STRUCTURE_IDS", "")
    )
    return frozenset(SEVEY_OWNED_STRUCTURE_IDS | extra)


def _as_date(value: Any) -> dt.date | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        return _parse_date(value)
    return None


def _observer_id(entry: Any) -> int | None:
    observer = getattr(entry, "observer", None)
    raw = getattr(observer, "obs_id", None) if observer is not None else None
    if raw is None:
        raw = getattr(entry, "obs_id", None)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def resolve_sevey_miner_ids(*, force: bool = False) -> frozenset[int]:
    """Character IDs treated as Sevey (main + Auth alts)."""
    global _sevey_miner_ids_cache
    if _sevey_miner_ids_cache is not None and not force:
        return _sevey_miner_ids_cache

    ids = {SEVEY_MAIN_CHARACTER_ID}
    ids |= _parse_int_set(os.environ.get("AA_MININGTAXES_SEVEY_CHARACTER_IDS", ""))

    usernames = {
        n.strip().lower()
        for n in os.environ.get("AA_MININGTAXES_SEVEY_USERNAMES", "sevey").split(",")
        if n.strip()
    } or set(SEVEY_USERNAMES)

    try:
        from allianceauth.eveonline.models import EveCharacter
        from django.contrib.auth.models import User

        users = list(User.objects.filter(username__iexact="sevey"))
        for name in usernames:
            users.extend(User.objects.filter(username__iexact=name))
        user_ids = {u.pk for u in users}
        if user_ids:
            ids.update(
                EveCharacter.objects.filter(
                    character_ownership__user_id__in=user_ids
                ).values_list("character_id", flat=True)
            )
        ids.update(
            EveCharacter.objects.filter(character_name__iexact="sevey").values_list(
                "character_id", flat=True
            )
        )
        # Any alt on the same Auth account as a known Sevey character.
        owner_ids = list(
            EveCharacter.objects.filter(character_id__in=ids).values_list(
                "character_ownership__user_id", flat=True
            )
        )
        owner_ids = [oid for oid in owner_ids if oid]
        if owner_ids:
            ids.update(
                EveCharacter.objects.filter(
                    character_ownership__user_id__in=owner_ids
                ).values_list("character_id", flat=True)
            )
    except Exception:
        logger.debug(
            "miningtaxes_structure_exclusions: Sevey character lookup deferred",
            exc_info=True,
        )

    _sevey_miner_ids_cache = frozenset(int(i) for i in ids if i)
    return _sevey_miner_ids_cache


def is_sevey_miner(miner_id: int, sevey_ids: Iterable[int] | None = None) -> bool:
    try:
        mid = int(miner_id)
    except (TypeError, ValueError):
        return False
    known = (
        frozenset(int(i) for i in sevey_ids)
        if sevey_ids is not None
        else resolve_sevey_miner_ids()
    )
    return mid in known


def observer_log_is_taxable(
    entry: Any,
    *,
    sevey_ids: Iterable[int] | None = None,
    cutoff: dt.date | None = None,
    start: dt.date | None = None,
) -> bool:
    """True if this observer log should count toward miningtaxes."""
    when = _as_date(getattr(entry, "date", None))
    if when is None or when < (start or moon_tax_start_date()):
        return False

    struct_cutoff = cutoff or effective_date()
    if when < struct_cutoff:
        return True

    obs_id = _observer_id(entry)
    if obs_id is None:
        return True
    if obs_id in ignore_all_structure_ids():
        return False
    if obs_id in sevey_owned_structure_ids():
        miner_id = getattr(entry, "miner_id", None)
        return not is_sevey_miner(miner_id, sevey_ids)
    return True


def _apply_taxable_ratio(row: Any, taxable_qty: int, total_qty: int) -> bool:
    """Scale or zero taxes when some/all volume is from excluded structures."""
    if total_qty <= 0 or taxable_qty <= 0:
        if float(getattr(row, "taxes_owed", 0) or 0) == 0.0 and float(
            getattr(row, "taxed_value", 0) or 0
        ) == 0.0:
            return False
        row.taxed_value = 0.0
        row.taxes_owed = 0.0
        row.save()
        return True
    if taxable_qty >= total_qty:
        return False
    ratio = taxable_qty / total_qty
    row.taxed_value = round(float(row.taxed_value or 0) * ratio, 2)
    row.taxes_owed = round(float(row.taxes_owed or 0) * ratio, 2)
    row.save()
    return True


def add_corp_moon_taxes_by_char(character) -> None:
    from miningtaxes.models import AdminMiningObsLog, CharacterMiningLedgerEntry

    entries = AdminMiningObsLog.objects.filter(
        miner_id=character.eve_character.character_id
    ).select_related("observer")

    sevey_ids = resolve_sevey_miner_ids()
    cutoff = effective_date()
    start = moon_tax_start_date()
    consolidate: dict[str, dict[str, int]] = {}
    for entry in entries:
        key = f"{entry.date}\t{entry.eve_solar_system_id}\t{entry.eve_type_id}"
        bucket = consolidate.setdefault(key, {"total": 0, "taxable": 0})
        qty = int(entry.quantity or 0)
        bucket["total"] += qty
        if observer_log_is_taxable(
            entry, sevey_ids=sevey_ids, cutoff=cutoff, start=start
        ):
            bucket["taxable"] += qty

    changed = False
    for key, bucket in consolidate.items():
        edate, esys, etype = key.split("\t")
        total_qty = bucket["total"]
        taxable_qty = bucket["taxable"]
        exclusion_applies = taxable_qty < total_qty
        try:
            row = character.mining_ledger.get(
                date=edate,
                eve_solar_system_id=esys,
                eve_type_id=etype,
            )
            if row.quantity != total_qty:
                row.quantity = total_qty
                row.save()
                row.calc_prices(corpmoon=True)
                changed = True
            elif exclusion_applies or (
                taxable_qty == 0 and float(row.taxes_owed or 0) > 0
            ):
                row.calc_prices(corpmoon=True)
                changed = True
            elif not exclusion_applies:
                continue
        except CharacterMiningLedgerEntry.DoesNotExist:
            row = character.mining_ledger.create(
                date=edate,
                eve_solar_system_id=esys,
                eve_type_id=etype,
                quantity=total_qty,
            )
            row.calc_prices(corpmoon=True)
            changed = True
        if _apply_taxable_ratio(row, taxable_qty, total_qty):
            changed = True

    if changed:
        character.calc_lifetime_taxes()
        character.calc_monthly_taxes()
        if hasattr(character, "calc_monthly_mining"):
            character.calc_monthly_mining()


def _zero_pre_start_moon_ledger_taxes() -> int:
    """Drop taxes on moon-ore ledger rows dated before the moon-tax start."""
    from miningtaxes.helpers import PriceGroups
    from miningtaxes.models import CharacterMiningLedgerEntry

    start = moon_tax_start_date()
    qs = CharacterMiningLedgerEntry.objects.filter(
        date__lt=start,
        eve_type__group_id__in=PriceGroups.moon_ore_groups,
    ).exclude(taxes_owed=0, taxed_value=0)
    return int(qs.update(taxes_owed=0.0, taxed_value=0.0))


def reapply_structure_exclusions(*, refresh_stats: bool = True) -> dict[str, int]:
    """Re-merge corp moon taxes so existing excluded charges are dropped."""
    from miningtaxes.models import Character
    from miningtaxes.tasks import add_corp_moon_taxes

    cleared = _zero_pre_start_moon_ledger_taxes()
    add_corp_moon_taxes()
    refreshed = 0
    for character in Character.objects.select_related("eve_character").iterator():
        character.calc_lifetime_taxes()
        character.calc_monthly_taxes()
        if hasattr(character, "calc_monthly_mining"):
            character.calc_monthly_mining()
        refreshed += 1
    if refresh_stats:
        from miningtaxes.models import Stats

        Stats.load().precalc_all()
    return {"characters": refreshed, "pre_start_rows_cleared": cleared}


def apply_miningtaxes_structure_exclusion_patch() -> None:
    try:
        from miningtaxes import tasks as mt_tasks
    except ImportError:
        return
    if getattr(mt_tasks, "_eve_emu_structure_exclusions_patched", False):
        return

    mt_tasks.add_corp_moon_taxes_by_char = add_corp_moon_taxes_by_char
    mt_tasks._eve_emu_structure_exclusions_patched = True
    logger.info(
        "miningtaxes_structure_exclusions: no moon tax before %s; "
        "ignore %s structures from %s (Sevey-owned %s remain taxable for others)",
        moon_tax_start_date().isoformat(),
        len(ignore_all_structure_ids()),
        effective_date().isoformat(),
        len(sevey_owned_structure_ids()),
    )
