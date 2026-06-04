"""Generate test EMU Moons invoices for recent pops (no mail/Discord).

Uses personal mining ledgers in each pop's system during the 48h window and
attributes volume to a representative moon ore for that pop's rarity. For UI /
workflow testing only — not production tax data.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from emu_moons.models import EmuExtraction, EmuInvoice, EmuMoonsSettings, StructureClass
from emu_moons.services.invoices import generate_invoices_for_extraction, refresh_penalties
from emu_moons.services.test_ledger import sync_test_extraction_ledger

from emu_moons.testing import TEST_MM_ID_BASE, TEST_MM_ID_SPAN

_POP_LINE = re.compile(
    r"^([A-Z0-9-]+\s+.+?)\s+(R\d+)\s+(\d{4})-(\w{3})-(\d{1,2})\s+(\d{1,2}:\d{2})",
    re.I,
)
_MONTH = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_SYSTEM_FROM_LABEL = re.compile(r"^([A-Z0-9-]+)")


def _default_pops_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "moon_pops.txt"


def _pops_from_mining_weeks(
    *,
    min_days: int = 0,
    max_days: int = 30,
) -> list[dict]:
    """One synthetic pop per ISO week per moon system that had AA-linked mining."""
    try:
        from miningtaxes.models import CharacterMiningLedgerEntry
    except ImportError:
        return []

    from emu_moons.services.moonmining_reports import _refinery_by_system_name
    from emu_moons.services.test_ledger import _system_prefix

    now = timezone.now()
    newest = now - timedelta(days=min_days)
    oldest = now - timedelta(days=max_days)
    systems = set(_refinery_by_system_name().keys())
    if not systems:
        return []

    qs = (
        CharacterMiningLedgerEntry.objects.filter(
            date__gte=oldest.date(),
            date__lte=newest.date(),
        )
        .select_related("eve_solar_system", "character__eve_character__character_ownership")
        .order_by("date")
    )
    weeks: dict[tuple[str, int, int], datetime] = {}
    for row in qs.iterator(chunk_size=3000):
        try:
            if not row.character.eve_character.character_ownership.user_id:
                continue
        except Exception:
            continue
        sys = _system_prefix(row.eve_solar_system.name if row.eve_solar_system_id else "")
        if sys not in systems:
            continue
        d = row.date
        key = (sys, d.isocalendar().year, d.isocalendar().week)
        popped = datetime(
            d.year,
            d.month,
            d.day,
            18,
            0,
            tzinfo=timezone.utc,
        )
        if key not in weeks or popped > weeks[key]:
            weeks[key] = popped

    pops = []
    for (sys, _y, _w), popped in sorted(weeks.items(), key=lambda x: x[1]):
        if popped > newest:
            continue
        if popped < oldest:
            continue
        pops.append(
            {
                "moon_label": f"{sys} - test week",
                "system_name": sys,
                "moon_number": None,
                "rarity": "r16",
                "popped_at": popped,
            }
        )
    return pops


def _parse_pops(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _POP_LINE.match(line)
        if not m:
            continue
        label, rarity, year, mon, day, hm = m.groups()
        month = _MONTH.get(mon.lower()[:3])
        if not month:
            continue
        hour, minute = (int(x) for x in hm.split(":")[:2])
        if hour >= 24:
            hour = 23
            minute = 59
        popped = datetime(
            int(year),
            month,
            int(day),
            hour,
            minute,
            tzinfo=timezone.utc,
        )
        sys_m = _SYSTEM_FROM_LABEL.match(label.strip())
        system = sys_m.group(1) if sys_m else label.split()[0]
        moon_m = re.search(r"Moon\s+(\d+)", label, re.I)
        rows.append(
            {
                "moon_label": label.strip(),
                "system_name": system,
                "moon_number": int(moon_m.group(1)) if moon_m else None,
                "rarity": rarity.lower(),
                "popped_at": popped,
            }
        )
    return rows


class Command(BaseCommand):
    help = (
        "Create test extractions + invoices for pops in the past N days. "
        "Uses character mining volume in each system (test moon ore lines). "
        "No EVE mail or Discord."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Include pops within this many days of now (default 30). Ignored if --min-days set.",
        )
        parser.add_argument(
            "--min-days",
            type=int,
            default=0,
            help="Newest pop age in days (0 = now). Use 60 with --max-days 90 for ~2 months ago.",
        )
        parser.add_argument(
            "--max-days",
            type=int,
            default=0,
            help="Oldest pop age in days (0 = use --days). E.g. 90 with --min-days 60.",
        )
        parser.add_argument(
            "--id-offset",
            type=int,
            default=0,
            help="Added to test moonmining_extraction_id (avoid clashes between runs).",
        )
        parser.add_argument(
            "--overdue-for-naughty",
            action="store_true",
            help="Set due dates past grace period and refresh penalties for naughty list.",
        )
        parser.add_argument(
            "--pops-file",
            type=str,
            default="",
            help="Tab-separated pop schedule (default: scripts/data/moon_pops_jun_jul_2026.txt).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing test extractions/invoices in the date window first.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max pops to process (0 = all in window).",
        )
        parser.add_argument(
            "--include-upcoming",
            action="store_true",
            help="Include scheduled pops after today (from pops file only).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        cfg = EmuMoonsSettings.load()
        now = timezone.now()
        min_days = max(0, options["min_days"])
        max_days = options["max_days"] or max(1, options["days"])
        if max_days < min_days:
            max_days, min_days = min_days, max_days
        newest = now - timedelta(days=min_days)
        oldest = now - timedelta(days=max_days)
        id_offset = int(options["id_offset"] or 0)
        pops_path = Path(options["pops_file"]) if options["pops_file"] else _default_pops_path()
        pops = _parse_pops(pops_path)
        pops = [p for p in pops if oldest <= p["popped_at"] <= newest]
        if not options["include_upcoming"]:
            pops = [p for p in pops if p["popped_at"] <= now]
        pops.sort(key=lambda p: p["popped_at"])

        if not pops:
            pops = _pops_from_mining_weeks(min_days=min_days, max_days=max_days)
            if pops:
                self.stdout.write(
                    f"No schedule rows in window; using {len(pops)} week(s) "
                    "with character mining in moon systems."
                )

        if options["limit"] > 0:
            pops = pops[: options["limit"]]

        if not pops:
            self.stdout.write(
                self.style.WARNING(
                    f"No pops between {max_days} and {min_days} days ago from {pops_path}. "
                    "Try --include-upcoming or ensure miners logged on Alliance Auth."
                )
            )
            return

        self.stdout.write(
            f"Pop window: {oldest.date()} → {newest.date()} "
            f"({len(pops)} pop(s), id offset {id_offset})"
        )

        if options["reset"]:
            test_ids = list(
                EmuExtraction.objects.filter(
                    moonmining_extraction_id__gte=TEST_MM_ID_BASE + id_offset,
                    moonmining_extraction_id__lt=TEST_MM_ID_BASE + id_offset + TEST_MM_ID_SPAN,
                    popped_at__gte=oldest,
                    popped_at__lte=newest,
                ).values_list("pk", flat=True)
            )
            inv_deleted, _ = EmuInvoice.objects.filter(extraction_id__in=test_ids).delete()
            ext_deleted, _ = EmuExtraction.objects.filter(pk__in=test_ids).delete()
            self.stdout.write(
                f"Removed {ext_deleted} test extraction(s) and {inv_deleted} invoice(s)."
            )

        touched_extraction_ids: list[int] = []
        total_invoices = 0
        total_extractions = 0
        for idx, pop in enumerate(pops):
            mm_id = TEST_MM_ID_BASE + id_offset + idx
            window_end = pop["popped_at"] + timedelta(hours=cfg.ledger_match_hours)
            ext, _ = EmuExtraction.objects.update_or_create(
                moonmining_extraction_id=mm_id,
                defaults={
                    "extraction_number": mm_id,
                    "moon_label": pop["moon_label"][:255],
                    "system_name": pop["system_name"][:128],
                    "moon_number": pop["moon_number"],
                    "structure_name": f"{pop['system_name']} - PUBLIC (test)",
                    "structure_class": StructureClass.PUBLIC,
                    "popped_at": pop["popped_at"],
                    "ledger_window_end": window_end,
                    "ore_composition_json": [{"rarity": pop["rarity"]}],
                    "invoices_generated": False,
                    "invoices_generated_at": None,
                    "discord_complete_sent": False,
                },
            )
            ext.moon_label = pop["moon_label"][:255]
            ext.system_name = pop["system_name"][:128]
            ext.moon_number = pop["moon_number"]
            ext.popped_at = pop["popped_at"]
            ext.ledger_window_end = window_end
            ext.ore_composition_json = [{"rarity": pop["rarity"]}]
            ext.invoices_generated = False
            ext.invoices_generated_at = None
            ext.invoices.all().delete()
            ext.save()

            ledger_rows = sync_test_extraction_ledger(ext)
            if ledger_rows == 0:
                self.stdout.write(
                    f"  {pop['moon_label']} ({pop['popped_at'].date()}): "
                    f"no miners in {pop['system_name']} window — skipped"
                )
                continue

            created = generate_invoices_for_extraction(
                ext,
                sync_ledger=False,
            )
            touched_extraction_ids.append(ext.pk)
            total_invoices += created
            total_extractions += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {pop['moon_label']} ({pop['popped_at'].date()}): "
                    f"{ledger_rows} miner(s), {created} invoice(s)"
                )
            )

        naughty_count = 0
        if options["overdue_for_naughty"] and touched_extraction_ids:
            overdue_due = timezone.now().date() - timedelta(
                days=cfg.grace_days_before_penalty + 7
            )
            updated = EmuInvoice.objects.filter(
                extraction_id__in=touched_extraction_ids,
                status=EmuInvoice.STATUS_OPEN,
            ).update(due_at=overdue_due)
            refresh_penalties()
            naughty_count = sum(
                1
                for inv in EmuInvoice.objects.filter(extraction_id__in=touched_extraction_ids)
                if inv.on_naughty_list
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Naughty list: {naughty_count} invoice(s) "
                    f"(due {overdue_due}, grace {cfg.grace_days_before_penalty} days, "
                    f"backdated {updated})."
                )
            )
            self.stdout.write("View: /emu-moons/naughty/")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Test run complete: {total_extractions} extraction(s), "
                f"{total_invoices} invoice(s) ({max_days}–{min_days} days ago)."
            )
        )
        self.stdout.write("View: /emu-moons/invoices/ (staff) or own invoices as a miner.")
        self.stdout.write(
            self.style.WARNING(
                "TEST DATA — from character ledgers + sample moon ore types, "
                "not corp mining observers."
            )
        )
