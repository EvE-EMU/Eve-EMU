"""
Application config
"""

# Django
from django.apps import AppConfig

# AA Theme Console
from aa_theme_console import __version__


class AaThemeConfig(AppConfig):
    """
    App config
    """

    name = "aa_theme_console"
    label = "aa_theme_console"
    verbose_name = f"Console like for Alliance Auth v{__version__}"
