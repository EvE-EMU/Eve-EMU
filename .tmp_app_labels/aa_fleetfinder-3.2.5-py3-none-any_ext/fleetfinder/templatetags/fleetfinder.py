"""
Versioned static URLs to break browser caches when changing the app version
"""

# Django
from django.template.defaulttags import register

# Alliance Auth
from allianceauth.services.hooks import get_extension_logger

# AA Fleet Finder
from fleetfinder import __title__
from fleetfinder.providers import AppLogger

logger = AppLogger(my_logger=get_extension_logger(__name__), prefix=__title__)


@register.filter
def get_item(dictionary: dict | None, key: str) -> str | None:
    """
    Little helper: get a key from a dictionary

    :param dictionary:
    :param key:
    :return:
    """

    if dictionary is None:
        return None

    return dictionary.get(key, None)
