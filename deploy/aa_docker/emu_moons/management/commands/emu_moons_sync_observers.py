"""Refresh Guns-R-Us corp mining observers and fix extraction system names."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from emu_moons.models import EmuExtraction
from emu_moons.services.observer_ledger import (
    ensure_observer_admin_characters,
    normalize_extraction_system_name,
    sync_corp_mining_observers_sync,
)


class Command(BaseCommand):
    help = (
        "Register Rexan (or AA_EMU_MOONS_OBSERVER_CHARACTERS) as miningtaxes admin "
        "and pull corp mining observer logs from ESI for EMU Moons invoicing."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--register-only",
            action="store_true",
            help="Only ensure AdminCharacter rows; do not call ESI.",
        )
        parser.add_argument(
            "--fix-system-names",
            action="store_true",
            help="Normalize EmuExtraction.system_name to solar system codes (e.g. 0TKF-6).",
        )

    def handle(self, *args, **options):
        if options["fix_system_names"]:
            fixed = 0
            for ext in EmuExtraction.objects.all().iterator():
                if normalize_extraction_system_name(ext):
                    fixed += 1
            self.stdout.write(f"Normalized system_name on {fixed} extraction(s).")

        admins = ensure_observer_admin_characters()
        self.stdout.write(
            f"Observer admin character(s): "
            f"{', '.join(a.eve_character.character_name for a in admins) or '(none)'}"
        )

        if options["register_only"]:
            return

        result = sync_corp_mining_observers_sync()
        self.stdout.write(
            f"Admin sync attempts: {result['updated']}, "
            f"AdminMiningObsLog rows: {result['log_rows']} "
            f"(+{result['new_rows']} new)"
        )
        for err in result.get("errors") or []:
            self.stdout.write(self.style.WARNING(err))
        if result["log_rows"] == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No observer logs yet. Rexan (or configured observer) needs "
                    "esi-industry.read_corporation_mining.v1, "
                    "esi-universe.read_structures.v1, and in-game Accountant/Director "
                    "role on Guns-R-Us, then re-login on auth."
                )
            )
        elif result["new_rows"]:
            self.stdout.write(self.style.SUCCESS("Corp observer logs updated."))
