from django.core.management.base import BaseCommand, CommandError

from buyback_v2.sync_structures import (
    DEFAULT_CHARACTER_NAME,
    sync_character_structures_to_buyback,
)
from buybackprogram.models import Owner


class Command(BaseCommand):
    help = (
        "Import structures a character can dock at into buybackprogram locations "
        "(public-universe probe + per-system search). Default character: sevey."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--character",
            default=DEFAULT_CHARACTER_NAME,
            help=f"Character name (default: {DEFAULT_CHARACTER_NAME}).",
        )
        parser.add_argument(
            "--owner-id",
            type=int,
            default=None,
            help="buybackprogram.Owner pk for new locations (default: buyback owner for user).",
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

    def handle(self, *args, **options):
        character_name = options["character"]
        owner = None
        if options["owner_id"]:
            owner = Owner.objects.filter(pk=options["owner_id"]).first()
            if owner is None:
                raise CommandError(f"buyback Owner id={options['owner_id']} not found.")
        else:
            owner = Owner.objects.filter(user__username__iexact=character_name).first()

        try:
            stats = sync_character_structures_to_buyback(
                character_name=character_name,
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
                f"{prefix}{character_name}: "
                f"{stats['created']} created, {stats['updated']} updated, "
                f"{stats['skipped']} skipped, "
                f"{stats['attached_links']} new program↔location links."
            )
        )
