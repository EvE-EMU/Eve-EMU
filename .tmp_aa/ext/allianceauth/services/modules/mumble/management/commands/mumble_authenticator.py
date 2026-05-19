from allianceauth.services.modules.mumble import authenticator

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Run the Mumble Authenticator'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--server_id', action='store', default=1,
            help='Run the Mumble Authenticator for the given Server Configuration ID')

    def handle(self, *args, **options) -> None:
        authenticator.main()
