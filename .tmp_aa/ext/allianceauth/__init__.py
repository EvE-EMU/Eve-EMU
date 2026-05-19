"""An auth system for EVE Online to help in-game organizations
manage online service access.
"""

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.

__version__ = '5.0.1'
__title__ = 'Alliance Auth'
__title_useragent__ = 'AllianceAuth'
__url__ = 'https://gitlab.com/allianceauth/allianceauth'
__esi_compatibility_date__ = "2025-12-16"
NAME = f'{__title__} v{__version__}'
