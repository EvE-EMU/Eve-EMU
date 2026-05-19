from django.core.management.base import BaseCommand, CommandError

from sde_wiki.wikijs_client import (
    ESI_THEME_HEAD,
    WikiJsClient,
    WikiJsClientError,
    load_esi_theme_css,
)


class Command(BaseCommand):
    help = "Apply EVE ESI / Swagger UI inspired dark theme to Wiki.js (inject CSS + fonts)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--throttle-ms",
            type=int,
            default=0,
            help="Delay between GraphQL calls.",
        )

    def handle(self, *args, **options):
        try:
            client = WikiJsClient(throttle_ms=options["throttle_ms"])
            css = load_esi_theme_css()
        except WikiJsClientError as exc:
            raise CommandError(str(exc)) from exc

        try:
            client.apply_theming(
                inject_css=css,
                inject_head=ESI_THEME_HEAD.strip(),
                dark_mode=True,
            )
        except WikiJsClientError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Applied EVE ESI theme (dark mode, custom CSS, Source Sans / Code Pro fonts)."
            )
        )
