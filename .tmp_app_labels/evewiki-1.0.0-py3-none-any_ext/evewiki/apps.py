from django.apps import AppConfig

from . import __version__


class EveWikiConfig(AppConfig):
    name = "evewiki"
    label = "evewiki"
    verbose_name = f"evewiki v{__version__}"
