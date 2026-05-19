"""Celery application for EvE-EMU Django stack (industrial / AA workers)."""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eve_emu.settings")

app = Celery("eve_emu")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
