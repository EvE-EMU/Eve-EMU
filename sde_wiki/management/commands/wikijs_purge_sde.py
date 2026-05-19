from django.core.management.base import BaseCommand, CommandError

from sde_wiki.wikijs_client import WikiJsClient, WikiJsClientError


class Command(BaseCommand):
    help = "Delete all Wiki.js pages under /sde (or another prefix) for a clean SDE re-import."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prefix",
            default="sde",
            help="Page path prefix to delete (default: sde).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Required confirmation; without this, only prints how many pages would be removed.",
        )
        parser.add_argument(
            "--via-db",
            action="store_true",
            help="Count/delete via Wiki.js Postgres (finds all rows; use when API preload is incomplete).",
        )
        parser.add_argument(
            "--throttle-ms",
            type=int,
            default=0,
            help="Delay after each GraphQL call.",
        )

    def handle(self, *args, **options):
        prefix = options["prefix"].strip("/")
        use_db = options["via_db"]

        if use_db:
            try:
                from sde_wiki.wiki_db import count_pages_under_prefix, purge_pages_via_db
            except ImportError as exc:
                raise CommandError(f"Database purge unavailable: {exc}") from exc
            try:
                found = count_pages_under_prefix(prefix)
            except Exception as exc:
                raise CommandError(f"Wiki.js DB query failed: {exc}") from exc
        else:
            try:
                client = WikiJsClient(throttle_ms=options["throttle_ms"])
                found = client.preload_paths(prefix)
            except WikiJsClientError as exc:
                raise CommandError(str(exc)) from exc

        self.stdout.write(f"Found {found:,} page(s) under /{prefix}")

        if not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run only. Re-run with --force to delete these pages."
                )
            )
            if not use_db and found < 10:
                self.stdout.write(
                    self.style.WARNING(
                        "API found very few pages; try --via-db if thousands still exist in Wiki.js."
                    )
                )
            return

        if use_db:
            self.stdout.write(
                self.style.WARNING(f"Deleting all /{prefix} pages via Postgres…")
            )
            try:
                from sde_wiki.wiki_db import purge_pages_via_db

                deleted = purge_pages_via_db(prefix)
            except Exception as exc:
                raise CommandError(f"Wiki.js DB purge failed: {exc}") from exc
            try:
                client = WikiJsClient(throttle_ms=options["throttle_ms"])
                client.rebuild_page_tree()
                client.flush_wiki_cache()
            except WikiJsClientError:
                pass
        else:
            def progress(done: int, total: int, path: str) -> None:
                if done == 1 or done % 100 == 0 or done == total:
                    self.stdout.write(f"  deleted {done:,}/{total:,} — {path}")

            self.stdout.write(self.style.WARNING(f"Deleting all /{prefix} pages…"))
            try:
                deleted = client.purge_paths(prefix, progress_callback=progress)
            except WikiJsClientError as exc:
                raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted:,} page(s). Run wikijs_import_sde next."
            )
        )
