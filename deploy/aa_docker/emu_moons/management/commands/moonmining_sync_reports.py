"""Import moonmining Member Mining data and seed structure profiles."""

from django.core.management.base import BaseCommand

from emu_moons.services.moonmining_reports import (
    backfill_mining_ledger_from_miningtaxes,
    import_historical_member_ledger_from_characters,
    sync_miningtaxes_observers_sync,
    sync_moonmining_member_ledgers,
    sync_structure_profiles_from_refineries,
)


class Command(BaseCommand):
    help = (
        "Seed structure tax profiles (public/nationalized by default, not private), "
        "refresh miningtaxes corp observer logs, and import moonmining mining ledgers "
        "for /moonmining/reports Member Mining."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--profiles-only",
            action="store_true",
            help="Only create StructureTaxProfile rows from refineries.",
        )
        parser.add_argument(
            "--skip-miningtaxes",
            action="store_true",
            help="Do not refresh AdminMiningObsLog from ESI.",
        )
        parser.add_argument(
            "--skip-moonmining",
            action="store_true",
            help="Do not pull moonmining MiningLedgerRecord from ESI.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count refineries that would sync without calling ESI ledger import.",
        )
        parser.add_argument(
            "--backfill-only",
            action="store_true",
            help="Only copy existing AdminMiningObsLog into moonmining MiningLedgerRecord.",
        )
        parser.add_argument(
            "--from-character-ledger",
            action="store_true",
            help="Import miningtaxes CharacterMiningLedgerEntry into moonmining (test/historical).",
        )
        parser.add_argument("--year", type=int, help="Single month import (with --month).")
        parser.add_argument("--month", type=int, help="Single month import (1–12).")
        parser.add_argument(
            "--months",
            type=int,
            default=4,
            help="When not using --year/--month, span this many months (default 4).",
        )
        parser.add_argument(
            "--all-systems",
            action="store_true",
            help="Include ledger rows outside tracked refinery systems.",
        )

    def handle(self, *args, **options):
        created = sync_structure_profiles_from_refineries()
        self.stdout.write(f"Structure profiles: {created} new (all refineries ensured)")

        if options["profiles_only"]:
            return

        if options["backfill_only"]:
            n = backfill_mining_ledger_from_miningtaxes()
            self.stdout.write(self.style.SUCCESS(f"Backfilled {n} new mining ledger rows"))
            return

        if options["from_character_ledger"]:
            stats = import_historical_member_ledger_from_characters(
                year=options.get("year"),
                month=options.get("month"),
                months=options["months"],
                moon_systems_only=not options["all_systems"],
            )
            self.stdout.write(
                f"Character ledger import {stats.get('start')} → {stats.get('end')}: "
                f"{stats.get('created', 0)} created, {stats.get('updated', 0)} updated, "
                f"{stats.get('skipped', 0)} skipped"
            )
            if stats.get("reason"):
                self.stdout.write(self.style.WARNING(stats["reason"]))
            elif stats.get("created") or stats.get("updated"):
                self.stdout.write(self.style.SUCCESS("Member Mining ledger populated."))
            return

        if not options["skip_miningtaxes"]:
            self.stdout.write(
                "Refreshing Guns-R-Us corp mining observers (Rexan / miningtaxes)…"
            )
            n = sync_miningtaxes_observers_sync()
            self.stdout.write(self.style.SUCCESS(f"Observer admin sync runs: {n}"))

        if not options["skip_moonmining"]:
            self.stdout.write("Importing moonmining member mining ledgers (non-private moons)…")
            stats = sync_moonmining_member_ledgers(dry_run=options["dry_run"])
            self.stdout.write(
                f"Refineries synced: {stats['refineries_synced']}, "
                f"ledger rows on synced refineries: {stats['ledger_rows']}"
            )
            for err in stats["errors"]:
                self.stdout.write(self.style.WARNING(err))
            if stats["errors"]:
                self.stdout.write(
                    self.style.WARNING(
                        "Some refineries failed — check Owner ESI tokens and "
                        "esi-industry.read_corporation_mining.v1."
                    )
                )
            elif stats["refineries_synced"] and stats["ledger_rows"]:
                self.stdout.write(self.style.SUCCESS("Member Mining report data imported."))
            elif stats["refineries_synced"] and not stats["ledger_rows"]:
                self.stdout.write(
                    "Ledgers updated but no rows yet — mining may be empty or "
                    "miners are not on Alliance Auth (user_id on ledger)."
                )

        n_backfill = backfill_mining_ledger_from_miningtaxes()
        if n_backfill:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Backfilled {n_backfill} moonmining ledger rows from miningtaxes logs."
                )
            )

        hist = import_historical_member_ledger_from_characters(
            months=options["months"],
            moon_systems_only=not options["all_systems"],
        )
        if hist.get("created") or hist.get("updated"):
            self.stdout.write(
                self.style.SUCCESS(
                    f"Historical character ledger: {hist['created']} created, "
                    f"{hist['updated']} updated ({hist.get('start')} → {hist.get('end')})"
                )
            )
