"""WSGI config for EvE-EMU Django (Alliance Auth / industry_suite)."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eve_emu.settings")

application = get_wsgi_application()
