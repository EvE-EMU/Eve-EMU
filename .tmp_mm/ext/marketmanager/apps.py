from django.apps import AppConfig

from . import __version__


class MarketManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = "marketmanager"
    verbose_name = f'AA Market Manager v{__version__}'
