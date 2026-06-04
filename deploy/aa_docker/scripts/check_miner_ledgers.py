"""One-off: compare monthly mining ledger totals for test miners."""
import calendar
import datetime as dt

from allianceauth.eveonline.models import EveCharacter
from django.db.models import Sum

from miningtaxes.models import AdminMiningObsLog, Character, CharacterMiningLedgerEntry

TARGETS = {
    "Yvain Dragonheart": None,
    "Nella Arkonor": None,
    "Rahul Sihg": 2124278663,
    "Ryald": 2113929817,
    "Hairlokk": None,
    "Alex Sukorov": 94165171,
    "Aieykins": 2124157015,
    "Akafes Fera": None,
}

EXPECTED = {
    "Yvain Dragonheart": {
        (2026, 3): (8_281_250, 2.0e9),
        (2026, 4): (3_622_070, 943.3e6),
        (2026, 5): (5_537_340, 3.0e9),
        (2026, 6): (214_610, 253.3e6),
    },
    "Nella Arkonor": {
        (2026, 3): (1_552_890, 926.3e6),
        (2026, 4): (448_950, 357.5e6),
        (2026, 5): (1_546_680, 1.2e9),
        (2026, 6): (73_000, 86.2e6),
    },
    "Rahul Sihg": {
        (2026, 3): (0, 0),
        (2026, 4): (0, 0),
        (2026, 5): (7_618_360, 1.5e9),
        (2026, 6): (435_550, 76.2e6),
    },
    "Ryald": {
        (2026, 3): (0, 0),
        (2026, 4): (0, 0),
        (2026, 5): (1_040_920, 160.8e6),
        (2026, 6): (463_350, 42.4e6),
    },
    "Hairlokk": {
        (2026, 3): (0, 0),
        (2026, 4): (0, 0),
        (2026, 5): (0, 0),
        (2026, 6): (373_280, 35.7e6),
    },
    "Alex Sukorov": {
        (2026, 3): (0, 0),
        (2026, 4): (999_890, 210.5e6),
        (2026, 5): (0, 0),
        (2026, 6): (350_700, 31.5e6),
    },
    "Aieykins": {
        (2026, 3): (0, 0),
        (2026, 4): (0, 0),
        (2026, 5): (409_130, 86.9e6),
        (2026, 6): (0, 0),
    },
    "Akafes Fera": {
        (2026, 3): (17_670, 4.2e6),
        (2026, 4): (28_610, 7.1e6),
        (2026, 5): (20_000, 7.1e6),
        (2026, 6): (0, 0),
    },
}

MONTHS = [(2026, 3), (2026, 4), (2026, 5), (2026, 6)]


def fmt_isk(v):
    v = float(v or 0)
    if v >= 1e9:
        return f"{v / 1e9:.1f}b"
    if v >= 1e6:
        return f"{v / 1e6:.1f}m"
    if v >= 1e3:
        return f"{v / 1e3:.1f}k"
    return f"{v:.1f}"


def month_range(y, m):
    return dt.date(y, m, 1), dt.date(y, m, calendar.monthrange(y, m)[1])


def pct_diff(actual, expected):
    if expected == 0:
        return "—" if actual == 0 else "NEW"
    return f"{100 * (actual - expected) / expected:+.1f}%"


def run():
    targets = dict(TARGETS)
    for name in list(targets.keys()):
        if targets[name]:
            continue
        ec = EveCharacter.objects.filter(character_name__iexact=name).first()
        if ec:
            targets[name] = ec.character_id

    print(f"AdminMiningObsLog rows: {AdminMiningObsLog.objects.count()}")
    print(f"CharacterMiningLedgerEntry rows: {CharacterMiningLedgerEntry.objects.count()}")
    print(f"miningtaxes Characters: {Character.objects.count()}\n")

    for name, cid in targets.items():
        exp = EXPECTED.get(name, {})
        ch = None
        if cid:
            ec = EveCharacter.objects.filter(character_id=cid).first()
            ch = Character.objects.filter(eve_character=ec).first() if ec else None

        print(f"{'=' * 72}")
        print(f"{name}  char_id={cid}  miningtaxes_Character={ch.pk if ch else 'MISSING'}")
        if not ch and cid:
            any_row = CharacterMiningLedgerEntry.objects.filter(
                character__eve_character__character_id=cid
            ).exists()
            print(f"  Ledger rows by char_id: {any_row}")

        if not ch:
            print("  >>> No miningtaxes Character — cannot match your spreadsheet from this DB.\n")
            continue

        ch.calc_monthly_mining()
        monthly_val = ch.get_monthly_mining() or {}

        for y, m in MONTHS:
            s, e = month_range(y, m)
            agg = CharacterMiningLedgerEntry.objects.filter(
                character=ch, date__gte=s, date__lte=e
            ).aggregate(
                vol=Sum("quantity"),
                val=Sum("taxed_value"),
                val_taxable=Sum("taxed_value", filter=None),
            )
            vol = int(agg["vol"] or 0)
            val = float(agg["val"] or 0)

            mk = f"{y}-{m:02d}-01"
            mj = float(monthly_val.get(mk, 0) or 0)

            ev, eisk = exp.get((y, m), (None, None))
            vol_ok = "OK" if ev is not None and vol == ev else (
                f"DIFF (exp {ev:,})" if ev is not None else ""
            )
            val_ok = ""
            if eisk is not None and eisk > 0:
                val_ok = "OK" if abs(val - eisk) / eisk < 0.02 else f"DIFF (exp {fmt_isk(eisk)})"

            obs_vol = 0
            if cid:
                obs_vol = int(
                    AdminMiningObsLog.objects.filter(
                        miner_id=cid, date__gte=s, date__lte=e
                    ).aggregate(v=Sum("quantity"))["v"]
                    or 0
                )

            print(
                f"  {y}-{m:02d}  vol={vol:>10,} {vol_ok:18}  "
                f"taxed_value={fmt_isk(val):>8} {val_ok:22}  "
                f"monthly_mining_json={fmt_isk(mj):>8}  obs_vol={obs_vol:,}"
            )
        print()


if __name__ == "__main__":
    run()
