"""Runtime fixes for Indy Hub on Alliance Auth 5 / Django 5."""

from __future__ import annotations

import datetime
import logging

logger = logging.getLogger(__name__)


def patch_indy_hub_for_django5() -> None:
    """Restore ``django.utils.timezone.utc`` removed in Django 5.

    Indy Hub (manual refresh cooldown, online status, job notifications) still
    references ``timezone.utc``; without this shim, ``?refresh=1`` raises
    ``AttributeError`` on corporation blueprint pages.
    """
    from django.utils import timezone as django_timezone

    if getattr(django_timezone, "utc", None) is not None:
        return

    django_timezone.utc = datetime.timezone.utc  # type: ignore[attr-defined]
    logger.info("indy_hub_django_compat: restored django.utils.timezone.utc shim")
