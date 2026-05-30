"""Register post_save / post_delete hooks for configured models."""

from __future__ import annotations

import logging
import os

from django.apps import apps
from django.db.models.signals import post_delete, post_save

from aa_report_bridge.webhooks import queue_instance_change

logger = logging.getLogger(__name__)

_DEFAULT_WATCH = (
    "auth.User",
    "auth.Group",
    "eveonline.EveCharacter",
    "memberaudit.Character",
    "miningtaxes.Character",
)


def _watch_labels() -> list[str]:
    raw = os.environ.get("REPORT_BRIDGE_WATCH_MODELS", "").strip()
    if raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    return list(_DEFAULT_WATCH)


def _connect_model(app_label: str, model_name: str) -> None:
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        logger.debug("report_bridge: skip watch %s.%s (not installed)", app_label, model_name)
        return

    def on_save(sender, instance, created, **kwargs):
        queue_instance_change(instance, action="create" if created else "update")

    def on_delete(sender, instance, **kwargs):
        queue_instance_change(instance, action="delete")

    post_save.connect(on_save, sender=model, weak=False, dispatch_uid=f"report_bridge_save_{app_label}_{model_name}")
    post_delete.connect(on_delete, sender=model, weak=False, dispatch_uid=f"report_bridge_del_{app_label}_{model_name}")
    logger.info("report_bridge: watching %s.%s", app_label, model_name)


def connect_watchers() -> None:
    for label in _watch_labels():
        if "." not in label:
            continue
        app_label, model_name = label.split(".", 1)
        _connect_model(app_label, model_name)
