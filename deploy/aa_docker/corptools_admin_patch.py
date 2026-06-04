"""Patch CorpTools admin_create_tasks (interval + crontab ValidationError on django-celery-beat)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def patch_corptools_admin_create_tasks() -> None:
    from django.apps import apps

    if not apps.is_installed("corptools"):
        return

    from django.contrib import messages
    from django.contrib.auth.decorators import login_required, permission_required
    from django.shortcuts import redirect

    from corptools import views

    @login_required
    @permission_required("corptools.admin")
    def admin_create_tasks(request):
        from corptools_beat_schedule import apply_corptools_beat_schedule

        apply_corptools_beat_schedule()
        messages.info(
            request,
            "Created/Reset Character and Corporation periodic tasks (30 minute interval).",
        )
        return redirect("corptools:admin")

    views.admin_create_tasks = admin_create_tasks
    logger.debug("corptools_admin_patch: patched admin_create_tasks")
