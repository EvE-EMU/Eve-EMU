from django.core.management.base import BaseCommand, CommandError

from sde_wiki.wiki_db import (
    count_unrendered_pages,
    iter_unrendered_page_ids,
    repair_bulk_imported_pages,
)
from sde_wiki.wikijs_client import WikiJsClient, WikiJsClientError


class Command(BaseCommand):
    help = (
        "Render HTML for /sde pages imported via --via-db (fixes 'Page has no rendered version')."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--prefix",
            default="sde",
            help="Page path prefix (default: sde).",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=8,
            help="Parallel render jobs (default 8).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Render at most N pages (0 = all missing).",
        )
        parser.add_argument(
            "--skip-repair",
            action="store_true",
            help="Skip SQL repair of NULL publish date fields.",
        )

    def handle(self, *args, **options):
        prefix = options["prefix"].strip("/")
        try:
            client = WikiJsClient()
        except WikiJsClientError as exc:
            raise CommandError(str(exc)) from exc

        if not options["skip_repair"]:
            fixed = repair_bulk_imported_pages(prefix)
            self.stdout.write(f"Repaired row defaults on {fixed:,} page(s).")

        pending = count_unrendered_pages(prefix)
        if pending == 0:
            self.stdout.write(self.style.SUCCESS("All pages already have render HTML."))
            client.flush_wiki_cache()
            return

        limit = options["limit"] or pending
        self.stdout.write(
            self.style.NOTICE(
                f"Rendering {min(limit, pending):,} of {pending:,} page(s) "
                f"with {options['workers']} workers…"
            )
        )

        page_ids = []
        for page_id in iter_unrendered_page_ids(prefix):
            page_ids.append(page_id)
            if len(page_ids) >= limit:
                break

        def progress(done: int, total: int, _page_id: int) -> None:
            if done == 1 or done % 200 == 0 or done == total:
                self.stdout.write(f"  rendered {done:,}/{total:,}")

        try:
            ok, errors = client.render_pages(
                page_ids,
                workers=options["workers"],
                progress_callback=progress,
            )
        except WikiJsClientError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write("Flushing Wiki.js cache…")
        client.flush_wiki_cache()

        if errors:
            self.stdout.write(
                self.style.WARNING(
                    f"Done with errors: rendered={ok:,} failed={errors:,}. "
                    "Re-run to retry failed pages."
                )
            )
            raise CommandError(f"{errors} page(s) failed to render.")
        self.stdout.write(self.style.SUCCESS(f"Rendered {ok:,} page(s)."))
