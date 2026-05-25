"""Post daily open-project status digest to routed Discord channels."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Post one status message per still-open routed corp project (progress from ESI). "
        "Same job as the 2:30 PM Eastern Celery beat task."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Post again even if today's digest was already sent for a goal_id.",
        )

    def handle(self, *args, **options):
        from corp_project_discord import post_daily_outstanding_corp_project_digest

        result = post_daily_outstanding_corp_project_digest(force=options["force"])
        self.stdout.write(self.style.SUCCESS(str(result)))
