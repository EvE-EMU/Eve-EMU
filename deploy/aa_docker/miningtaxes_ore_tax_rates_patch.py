"""Make ``OrePrices.tax_rate`` policy-derived instead of a per-row admin field.

Root cause of two related bugs found while investigating incorrect mining tax
amounts (2026-09-11):

1. ``OrePrices.tax_rate`` defaults to 10.0 on the model, and
   ``miningtaxes.tasks.update_all_prices`` auto-creates an ``OrePrices`` row
   (at that 10.0 default) for essentially every ore/ice/gas/Abyssal-ore type
   CCP publishes -- not just moon ore. Since ``get_tax()`` uses the row's
   ``tax_rate`` whenever a row exists at all (only falling back to
   ``MININGTAXES_UNKNOWN_TAX_RATE`` when no row exists), raising
   ``MININGTAXES_UNKNOWN_TAX_RATE`` or dropping it to 0 has almost no real
   effect: nearly every ore already has a materialized row. Per policy, any
   ore type that is not one of our taxed moon-ore groups should not be taxed
   at all.

2. Within the taxed moon-ore groups themselves, only the *uncompressed* ore
   names had ever had their ``tax_rate`` hand-set to the intended R64/R32/R16
   rate via the admin. The *compressed* variants (what moon-mining
   refineries/Athanors/Tataras actually produce, and so what most real
   observer-log entries are) are a separate ``EveType``/``OrePrices`` row
   each, and were left sitting at the 10.0 model default -- e.g. "Compressed
   Loparite" (R64, should be 45%) was being taxed at 10%. This silently
   under-taxed the majority of real moon mining.

Fix: tax_rate is derived purely from the ore's reprocessing group via
``MOON_GROUP_TAX_RATES`` below, enforced on every ``OrePrices`` save (so it
self-heals for existing rows, newly created rows, and any new ore/compression
variant CCP adds later -- no per-row admin entry required, ever). Group IDs
match ``miningtaxes.helpers.PriceGroups.moon_ore_groups``.

Rate schedule confirmed by the user 2026-09-11 (JRV rates):
    R64 (group 1923): 45%
    R32 (group 1922): 30%
    R16 (group 1921): 15%
    R4  (group 1884): 10%
R8 (group 1920) was not listed in the user's rate schedule; per the user's
own stated policy ("any non listed ore type should not be taxed") it is
treated as untaxed (0%) here. Flagged explicitly to the user -- if R8 moons
are actually taxed too, just add its rate to MOON_GROUP_TAX_RATES.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# eve_type.group_id -> tax_rate percentage (matches OrePrices.tax_rate, which
# is a percentage like 45.0, not a fraction).
MOON_GROUP_TAX_RATES = {
    1923: 45.0,  # R64
    1922: 30.0,  # R32
    1921: 15.0,  # R16
    1920: 0.0,   # R8 - not in the user's rate schedule, treated as untaxed
    1884: 10.0,  # R4
}


def _intended_rate(eve_type) -> float:
    return MOON_GROUP_TAX_RATES.get(eve_type.group_id, 0.0)


def _pre_save_handler(sender, instance, **kwargs):
    try:
        intended = _intended_rate(instance.eve_type)
    except Exception:
        return
    if float(instance.tax_rate) != intended:
        instance.tax_rate = intended


def fix_existing_rows() -> dict:
    """One-time/repeatable bulk correction for rows already in the DB.

    Safe to call any time (e.g. after CCP adds new ore variants) -- it just
    re-derives every row's tax_rate from its group and only writes the ones
    that are wrong.
    """
    from miningtaxes.models import OrePrices

    changed = []
    for o in OrePrices.objects.select_related("eve_type").all():
        intended = _intended_rate(o.eve_type)
        if float(o.tax_rate) != intended:
            changed.append((o.eve_type.name, float(o.tax_rate), intended))
            o.tax_rate = intended
            o.save(update_fields=["tax_rate"])
    logger.info(
        "miningtaxes_ore_tax_rates_patch.fix_existing_rows: corrected %d rows",
        len(changed),
    )
    return {"corrected_count": len(changed), "corrected": changed}


def apply_miningtaxes_ore_tax_rates_patch() -> None:
    from django.db.models.signals import pre_save

    try:
        from miningtaxes.models import OrePrices
    except ImportError:
        return

    if getattr(OrePrices, "_eve_emu_tax_rate_patch_connected", False):
        return

    pre_save.connect(
        _pre_save_handler,
        sender=OrePrices,
        dispatch_uid="eve_emu_miningtaxes_ore_tax_rate_policy",
    )
    OrePrices._eve_emu_tax_rate_patch_connected = True
    logger.info(
        "miningtaxes_ore_tax_rates_patch: OrePrices.tax_rate is now derived "
        "from PriceGroups group id on every save (see MOON_GROUP_TAX_RATES)"
    )
