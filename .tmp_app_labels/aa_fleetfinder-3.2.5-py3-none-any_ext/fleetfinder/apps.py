"""
App config
"""

# Django
from django.apps import AppConfig
from django.utils.text import format_lazy

# AA Fleet Finder
from fleetfinder import __title_translated__, __version__


class FleetFinderConfig(AppConfig):
    """
    Application config
    """

    name = "fleetfinder"
    label = "fleetfinder"
    verbose_name = format_lazy(
        "{app_title} v{version}", app_title=__title_translated__, version=__version__
    )
