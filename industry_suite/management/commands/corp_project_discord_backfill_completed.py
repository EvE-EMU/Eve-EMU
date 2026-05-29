"""Backfill Discord alerts for completed D0 (etc.) corp manufacturing projects."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Post Discord alerts for corp projects that completed recently and match "
        "AA_CORP_PROJECT_DISCORD_COMPLETED_TIERS (default: d0) and routes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count matches without posting to Discord.",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Look back this many days (default: AA_CORP_PROJECT_DISCORD_BACKFILL_DAYS or 365).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ignore dedupe cache and post again.",
        )

    def handle(self, *args, **options):
        from corp_project_discord import backfill_completed_corp_project_discord

        result = backfill_completed_corp_project_discord(
            dry_run=options["dry_run"],
            days=options["days"],
            force=options["force"],
        )
        self.stdout.write(self.style.SUCCESS(str(result)))
