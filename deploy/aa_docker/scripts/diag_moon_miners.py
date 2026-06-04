"""Diagnose why moon miners are missing from reports/invoices."""
import datetime as dt

from allianceauth.authentication.models import CharacterOwnership
from django.utils import timezone

from emu_moons.services.moonmining_reports import _refinery_by_system_name
from miningtaxes.helpers import PriceGroups
from miningtaxes.models import AdminCharacter, AdminMiningObsLog, CharacterMiningLedgerEntry

start = dt.date(2026, 6, 1)
moon_g = set(PriceGroups.moon_ore_groups)
sys_names = set(_refinery_by_system_name().keys())

rows = CharacterMiningLedgerEntry.objects.filter(date__gte=start).select_related(
    "eve_type", "eve_type__group", "eve_solar_system", "character__eve_character"
)
by_char = {}
for r in rows:
    sys = (r.eve_solar_system.name or "").upper()
    if sys not in sys_names:
        continue
    cid = r.character.eve_character.character_id
    name = r.character.eve_character.character_name
    gid = r.eve_type.group_id if r.eve_type else 0
    is_moon = gid in moon_g
    by_char.setdefault(cid, {"name": name, "moon": 0, "belt": 0, "aa": False})
    if is_moon:
        by_char[cid]["moon"] += int(r.quantity or 0)
    else:
        by_char[cid]["belt"] += int(r.quantity or 0)

co = set(
    CharacterOwnership.objects.filter(
        character__character_id__in=by_char.keys()
    ).values_list("character__character_id", flat=True)
)
for cid in by_char:
    by_char[cid]["aa"] = cid in co

print(f"Miners in moon SYSTEMS (char ledger) since {start}: {len(by_char)}")
for cid, d in sorted(by_char.items(), key=lambda x: -(x[1]["moon"] + x[1]["belt"]))[:20]:
    print(
        f"  {d['name']:22} moon={d['moon']:>8} belt={d['belt']:>10} "
        f"on_AA={'yes' if d['aa'] else 'NO'}"
    )

print("\nAdminMiningObsLog before sync:", AdminMiningObsLog.objects.count())
for admin in AdminCharacter.objects.select_related("eve_character"):
    name = admin.eve_character.character_name
    corp = admin.eve_character.corporation_id
    print(f"\nAdmin: {name} corp={corp}")
    try:
        result = admin.update_mining_observers()
        print(f"  update_mining_observers: {result}")
    except Exception as exc:
        print(f"  ERROR: {type(exc).__name__}: {exc}")

print("\nAdminMiningObsLog after sync:", AdminMiningObsLog.objects.count())
if AdminMiningObsLog.objects.exists():
    from django.db.models import Count

    top = (
        AdminMiningObsLog.objects.filter(date__gte=start)
        .values("miner_id")
        .annotate(n=Count("id"))
        .order_by("-n")[:10]
    )
    print("Top miners in obs log this month:", list(top))
