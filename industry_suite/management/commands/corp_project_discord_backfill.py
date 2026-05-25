"""One-time backfill: post still-open D0/D1 corp projects to routed Discord webhooks."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Post Discord alerts for corp projects that are still open (created but not "
        "completed/closed) and match AA_CORP_PROJECT_DISCORD_ROUTES. Use on first enable."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be sent without posting to Discord.",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Only consider notifications within this many days (default: AA_CORP_PROJECT_DISCORD_BACKFILL_DAYS or 365). Use 0 for all time.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ignore dedupe cache and post again for the same goal_id.",
        )

    def handle(self, *args, **options):
        from corp_project_discord import backfill_outstanding_corp_project_discord

        result = backfill_outstanding_corp_project_discord(
            dry_run=options["dry_run"],
            days=options["days"],
            force=options["force"],
        )
        self.stdout.write(self.style.SUCCESS(str(result)))
