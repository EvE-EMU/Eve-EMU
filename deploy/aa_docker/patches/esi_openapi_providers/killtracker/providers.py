"""ESI provider for killtracker."""

from esi_clients_compat import openapi_esi_provider_from_app_info_text

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from killtracker import USER_AGENT_TEXT, __title__

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

esi = openapi_esi_provider_from_app_info_text(USER_AGENT_TEXT)
