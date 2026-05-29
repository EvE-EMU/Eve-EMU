"""Disable aa-miningtaxes Alliance Auth notifications when configured."""

from __future__ import annotations

import os


def _notifications_disabled() -> bool:
    return os.environ.get("AA_MININGTAXES_NOTIFY_ENABLED", "0").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    )


def apply_miningtaxes_notify_patch() -> None:
    if not _notifications_disabled():
        return
    try:
        from miningtaxes import tasks
    except ImportError:
        return
    if getattr(tasks, "_eve_emu_notify_patched", False):
        return

    def _noop(*_args, **_kwargs):
        return None

    for name in (
        "notify_taxes_due",
        "notify_second_taxes_due",
        "notify_current_taxes_threshold",
        "apply_interest",
    ):
        if hasattr(tasks, name):
            setattr(tasks, name, _noop)
    tasks._eve_emu_notify_patched = True
