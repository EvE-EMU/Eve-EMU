"""ESI client provider for Structures."""

import logging

from esi_clients_compat import openapi_esi_provider_from_app_info_text

from app_utils.logging import LoggerAddTag

from . import __title__, __version__

logger = LoggerAddTag(logging.getLogger(__name__), __title__)
esi = openapi_esi_provider_from_app_info_text(f"aa-structures v{__version__}")
