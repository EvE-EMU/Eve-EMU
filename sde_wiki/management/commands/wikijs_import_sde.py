from django.core.management.base import BaseCommand, CommandError

from sde_wiki.importer import SDEWikiImporter
from sde_wiki.wikijs_client import WikiJsClient, WikiJsClientError

SECTIONS = ("home", "map", "types", "dogma", "industry")


class Command(BaseCommand):
    help = (
        "Import the full EVE SDE (django-eveonline-sde) into Wiki.js under /sde. "
        "Requires WIKIJS_API_URL, WIKIJS_API_KEY, and a loaded SDE (manage.py esde_load_sde)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--section",
            action="append",
            choices=[*SECTIONS, "all"],
            help="Import only these sections (repeatable). Default: all.",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update pages that already exist (default is to skip existing pages).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count work only; do not call Wiki.js.",
        )
        parser.add_argument(
            "--fast",
            action="store_true",
            help=(
                "Skip ~52k type pages, ~8k solar-system pages, and dogma detail pages; "
                "types on group pages, systems on constellation pages. Recommended."
            ),
        )
        parser.add_argument(
            "--turbo",
            action="store_true",
            help=(
                "Parallel GraphQL writers (8 workers), no per-create tree settle. "
                "Use with --fast; rebuilds page tree once at the end."
            ),
        )
        parser.add_argument(
            "--published-types-only",
            action="store_true",
            help="Import only published item types (faster; full import only).",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=None,
            help="Parallel GraphQL writers (default 1, or 8 with --turbo).",
        )
        parser.add_argument(
            "--tree-settle-ms",
            type=int,
            default=None,
            help=(
                "Pause after each create (default 0; tree rebuilt once at end). "
                "Use 75 if you see pageTree FK errors without --turbo."
            ),
        )
        parser.add_argument(
            "--throttle-ms",
            type=int,
            default=0,
            help="Delay after each GraphQL call per worker (default 0).",
        )
        parser.add_argument(
            "--progress-interval",
            type=int,
            default=50,
            help="Log progress with ETA every N pages (default 50).",
        )
        parser.add_argument(
            "--render",
            action="store_true",
            help="Call pages.render after each write (slower; usually unnecessary).",
        )
        parser.add_argument(
            "--remainder",
            action="store_true",
            help=(
                "After a --fast import: solar systems, per-item-type and dogma detail pages, "
                "and refresh group/constellation/market-group index links. Default sections: map, types, dogma."
            ),
        )
        parser.add_argument(
            "--via-db",
            action="store_true",
            help=(
                "Write pages in batches to Wiki.js Postgres (fast). SDE data still comes "
                "from local eve_sde DB (manage.py esde_load_sde), not HTTP. Rebuilds tree via GraphQL once."
            ),
        )
        parser.add_argument(
            "--db-batch-size",
            type=int,
            default=500,
            help="Rows per INSERT batch when using --via-db (default 500).",
        )

    def handle(self, *args, **options):
        via_db = options["via_db"]
        remainder = options["remainder"]
        turbo = options["turbo"]
        workers = options["workers"]
        if workers is None:
            workers = 8 if turbo and not via_db else (4 if via_db else 1)
        tree_settle_ms = options["tree_settle_ms"]
        if tree_settle_ms is None:
            tree_settle_ms = 0

        if via_db and options["update_existing"]:
            raise CommandError(
                "--via-db only inserts new pages. Purge /sde first or omit --update-existing."
            )

        try:
            client = WikiJsClient(
                throttle_ms=options["throttle_ms"],
                render_after_write=options["render"],
                tree_settle_ms=tree_settle_ms,
                parallel_writes=workers > 1 and not via_db,
            )
        except WikiJsClientError as exc:
            raise CommandError(str(exc)) from exc

        db_writer = None
        if via_db and not options["dry_run"]:
            from sde_wiki.wiki_db import WikiDbBulkWriter

            db_writer = WikiDbBulkWriter(
                skip_existing=not options["update_existing"],
                batch_size=options["db_batch_size"],
            )

        raw_sections = options.get("section") or ["all"]
        if remainder:
            if "all" in raw_sections or not options.get("section"):
                sections = {"map", "types", "dogma"}
            else:
                sections = set(raw_sections)
        elif "all" in raw_sections:
            sections = set(SECTIONS)
        else:
            sections = set(raw_sections)

        skip_existing = not options["update_existing"]
        fast = options["fast"]
        if remainder and fast:
            self.stdout.write(
                self.style.WARNING("--remainder ignores --fast (imports detail pages).")
            )

        importer = SDEWikiImporter(
            client,
            skip_existing=skip_existing,
            dry_run=options["dry_run"],
            include_unpublished_types=not options["published_types_only"],
            stdout=self.stdout,
            progress_interval=options["progress_interval"],
            workers=workers,
            fast_import=fast,
            remainder_mode=remainder,
            db_writer=db_writer,
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Wiki.js SDE import: sections={sorted(sections)} "
                f"fast={fast} remainder={remainder} via_db={via_db} turbo={turbo} "
                f"workers={workers} tree_settle_ms={tree_settle_ms} "
                f"skip_existing={skip_existing} dry_run={options['dry_run']}"
            )
        )
        if via_db:
            self.stdout.write(
                self.style.NOTICE(
                    "SDE source: local Postgres (eve_sde). Wiki writes: batched SQL to wikijs DB."
                )
            )

        stats = importer.run(sections)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={stats.created} updated={stats.updated} "
                f"skipped={stats.skipped} dry_run={stats.dry_run} errors={stats.errors}"
            )
        )
        if stats.errors:
            raise CommandError(f"Import finished with {stats.errors} error(s).")
