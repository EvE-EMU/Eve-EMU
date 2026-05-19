from django.conf import settings

MUMBLE_TEMPS_SSO_PREFIX = getattr(settings, "MUMBLE_TEMPS_SSO_PREFIX", "[TEMP]")
