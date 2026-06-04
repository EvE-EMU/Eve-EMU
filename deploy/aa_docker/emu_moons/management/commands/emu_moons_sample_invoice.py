"""Generate sample EMU Moons invoices without EVE mail or Discord."""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from emu_moons.models import EmuExtraction, EmuInvoice, EmuMoonsSettings, StructureClass
from emu_moons.services.extractions import sync_extraction_ledger
from emu_moons.services.invoices import generate_invoices_for_extraction


class Command(BaseCommand):
    help = (
        "Create or reuse an extraction ~N days ago, sync ledger, generate invoices. "
        "Does not send EVE mail or Discord."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-ago",
            type=int,
            default=7,
            help="Target pop date relative to now (default 7 = last week).",
        )
        parser.add_argument(
            "--system",
            default="9SBB-9",
            help="Solar system for ledger matching (default 9SBB-9).",
        )
        parser.add_argument(
            "--extraction-id",
            type=int,
            help="Existing EmuExtraction PK (overrides --days-ago / --system).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing invoices for this extraction and regenerate.",
        )
        parser.add_argument(
            "--limit-invoices",
            type=int,
            default=0,
            help="Only invoice this many miners (0 = all with ledger + AA user).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        cfg = EmuMoonsSettings.load()
        extraction = self._resolve_extraction(options, cfg)
        if options["reset"]:
            deleted, _ = extraction.invoices.all().delete()
            extraction.invoices_generated = False
            extraction.invoices_generated_at = None
            extraction.discord_complete_sent = False
            extraction.save(
                update_fields=[
                    "invoices_generated",
                    "invoices_generated_at",
                    "discord_complete_sent",
                ]
            )
            self.stdout.write(f"Removed {deleted} existing invoice(s).")

        ledger_rows = sync_extraction_ledger(extraction)
        self.stdout.write(
            f"Extraction #{extraction.pk} {extraction.moon_label} "
            f"(pop {extraction.popped_at.date()}): {ledger_rows} ledger line(s)"
        )
        if ledger_rows == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No moon ore observer lines — nothing to invoice. "
                    "Run miningtaxes corp observer sync (AdminMiningObsLog) for a director "
                    "token with esi-industry.read_corporation_mining.v1. "
                    "Belt ores mined at moons (e.g. Kylixium) are not taxed."
                )
            )
            return

        if options["limit_invoices"] > 0:
            self._trim_ledger_lines(extraction, options["limit_invoices"])

        if extraction.invoices_generated and not options["reset"]:
            self.stdout.write(
                self.style.WARNING("Invoices already generated; use --reset to redo.")
            )
            self._print_invoices(extraction)
            return

        created = generate_invoices_for_extraction(extraction)
        self.stdout.write(self.style.SUCCESS(f"Created {created} invoice(s) (no mail/Discord)."))
        self._print_invoices(extraction)

    def _resolve_extraction(self, options, cfg: EmuMoonsSettings) -> EmuExtraction:
        if options.get("extraction_id"):
            return EmuExtraction.objects.get(pk=options["extraction_id"])

        pop = timezone.now() - timedelta(days=options["days_ago"])
        system = (options["system"] or "9SBB-9").strip()
        # moonmining_extraction_id is a 32-bit positive int — keep sample IDs in a safe range
        sample_mm_id = 9_000_000 + options["days_ago"]

        ext, created = EmuExtraction.objects.get_or_create(
            moonmining_extraction_id=sample_mm_id,
            defaults={
                "extraction_number": sample_mm_id,
                "moon_label": f"{system} - sample pop",
                "system_name": system[:128],
                "structure_name": f"{system} - PUBLIC (sample)",
                "structure_class": StructureClass.PUBLIC,
                "popped_at": pop,
                "ledger_window_end": pop + timedelta(hours=cfg.ledger_match_hours),
            },
        )
        if not created:
            ext.popped_at = pop
            ext.ledger_window_end = pop + timedelta(hours=cfg.ledger_match_hours)
            ext.system_name = system[:128]
            ext.save(update_fields=["popped_at", "ledger_window_end", "system_name"])
        return ext

    def _trim_ledger_lines(self, extraction: EmuExtraction, limit: int) -> None:
        keep_users: set[int] = set()
        for line in extraction.ledger_lines.filter(user_id__isnull=False).order_by(
            "miner_character_name"
        ):
            if line.user_id in keep_users:
                continue
            if len(keep_users) >= limit:
                break
            keep_users.add(line.user_id)
        removed, _ = (
            extraction.ledger_lines.exclude(user_id__in=keep_users).delete()
        )
        if removed:
            self.stdout.write(f"Trimmed to {limit} miner(s); dropped {removed} ledger row(s).")

    def _print_invoices(self, extraction: EmuExtraction) -> None:
        invoices = EmuInvoice.objects.filter(extraction=extraction).order_by(
            "-original_tax_isk"
        )
        if not invoices:
            return
        self.stdout.write("")
        self.stdout.write("Sample invoices:")
        for inv in invoices[:15]:
            self.stdout.write(
                f"  {inv.invoice_number}  {inv.character_name}  "
                f"tax {inv.original_tax_isk:,.2f} ISK  due {inv.due_at}  "
                f"status={inv.status}"
            )
        if invoices.count() > 15:
            self.stdout.write(f"  … and {invoices.count() - 15} more")
        first = invoices.first()
        self.stdout.write("")
        self.stdout.write(
            f"View: /emu-moons/invoices/{first.invoice_number}/ "
            f"(login as {first.user.username})"
        )
