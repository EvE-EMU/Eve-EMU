from django.core.management.base import BaseCommand, CommandError

from buyback_v2.sync_structures import GUNS_R_US_CORP_ID, sync_corp_structures_to_buyback
from buybackprogram.models import Owner, Program
from buyback_v2.models import ProgramPricingProfile


class Command(BaseCommand):
    help = (
        "Fetch Guns-R-Us (or other corp) structures from ESI "
        "GET /corporations/{corporation_id}/structures/ and register them as "
        "buybackprogram locations, optionally linking all buyback programs."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--corporation-id",
            type=int,
            default=GUNS_R_US_CORP_ID,
            help=f"Corporation ID (default: Guns-R-Us {GUNS_R_US_CORP_ID}).",
        )
        parser.add_argument(
            "--owner-id",
            type=int,
            default=None,
            help="buybackprogram.Owner pk for new locations (default: first owner).",
        )
        parser.add_argument(
            "--program-id",
            type=int,
            action="append",
            dest="program_ids",
            help="Only attach locations to these program pk(s). Default: all programs.",
        )
        parser.add_argument(
            "--no-attach",
            action="store_true",
            help="Create/update locations only; do not add to programs.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report counts without writing to the database.",
        )
        parser.add_argument(
            "--ensure-v2-profiles",
            action="store_true",
            help="Ensure buyback_v2 ProgramPricingProfile exists for each program.",
        )

    def handle(self, *args, **options):
        corp_id = options["corporation_id"]
        owner = None
        if options["owner_id"]:
            owner = Owner.objects.filter(pk=options["owner_id"]).first()
            if owner is None:
                raise CommandError(f"buyback Owner id={options['owner_id']} not found.")

        if options["ensure_v2_profiles"]:
            for program in Program.objects.all().iterator():
                ProgramPricingProfile.objects.get_or_create(program=program)
            self.stdout.write("Ensured buyback v2 pricing profiles.")

        try:
            stats = sync_corp_structures_to_buyback(
                corporation_id=corp_id,
                buyback_owner=owner,
                attach_programs=not options["no_attach"],
                program_ids=options["program_ids"],
                dry_run=options["dry_run"],
            )
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        prefix = "[dry-run] " if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Corp {corp_id}: "
                f"{stats['created']} created, {stats['updated']} updated, "
                f"{stats['skipped']} skipped, "
                f"{stats['attached_links']} new program↔location links."
            )
        )
