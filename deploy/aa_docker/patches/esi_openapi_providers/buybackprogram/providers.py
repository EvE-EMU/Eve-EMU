"""Shared ESI client for Buyback Program (django-esi 9 / OpenAPI)."""

from esi_clients_compat import openapi_esi_provider_from_app_info_text

from . import __version__

esi = openapi_esi_provider_from_app_info_text(f"aa-buyback-program v{__version__}")
