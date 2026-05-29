from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from moon_rentals.models import MoonPop, default_buyback_program_id
from moon_rentals.parsers import parse_import_text, resolve_owner


class Command(BaseCommand):
    help = "Import moon pop schedule from a text file (tab-separated location and datetime)."

    def add_arguments(self, parser):
        parser.add_argument("file", type=str, help="Path to text file inside container")
        parser.add_argument(
            "--kind",
            choices=[MoonPop.CORP_FALSE_GODS, MoonPop.PRIVATE],
            default=MoonPop.CORP_FALSE_GODS,
        )
        parser.add_argument("--owner", type=str, default="", help="Default Auth username for private moons")
        parser.add_argument("--program-id", type=int, default=None)

    def handle(self, *args, **options):
        program_id = options["program_id"] or default_buyback_program_id()
        with open(options["file"], encoding="utf-8") as fh:
            text = fh.read()
        created = 0
        for row in parse_import_text(
            text,
            default_kind=options["kind"],
            default_owner_username=options["owner"] or None,
        ):
            owner = resolve_owner(row.private_owner_username)
            if row.rental_kind == MoonPop.PRIVATE and not owner:
                self.stderr.write(
                    f"Line {row.line_no}: unknown user {row.private_owner_username}"
                )
                continue
            _, was_created = MoonPop.objects.get_or_create(
                location_label=row.location_label,
                pop_at=row.pop_at,
                defaults={
                    "system_name": row.system_name,
                    "moon_number": row.moon_number,
                    "rental_kind": row.rental_kind,
                    "private_owner": owner,
                    "buyback_program_id": program_id,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(f"Added {row.location_label} @ {row.pop_at}")
        self.stdout.write(self.style.SUCCESS(f"Created {created} moon pop(s)"))
