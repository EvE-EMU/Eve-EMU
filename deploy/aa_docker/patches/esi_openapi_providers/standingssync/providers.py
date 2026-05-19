"""ESI client for standingssync."""

from esi_clients_compat import openapi_esi_provider_from_app_info_text

from . import __version__

esi = openapi_esi_provider_from_app_info_text(f"aa-standingssync v{__version__}")
