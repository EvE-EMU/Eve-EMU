"""Patch aa-taskmonitor: per-task Kill button on queued tasks admin list."""

from __future__ import annotations


def patch_taskmonitor_kill_queued_task() -> None:
    from django.contrib import admin
    from django.urls import reverse
    from django.utils import html

    from taskmonitor.admin import QueuedTaskAdmin

    if getattr(QueuedTaskAdmin, "_eve_emu_kill_patched", False):
        return

    @admin.display(description="")
    def _kill_action(self, obj) -> str:
        url = reverse("taskmonitor:admin_queued_task_kill", args=[obj.id])
        return html.format_html(
            '<a class="button" href="{}" '
            "onclick=\"return confirm('Remove this task from the Celery queue?');\">Kill</a>",
            url,
        )

    QueuedTaskAdmin.list_display = (*QueuedTaskAdmin.list_display, "_kill_action")
    QueuedTaskAdmin._kill_action = _kill_action
    QueuedTaskAdmin._eve_emu_kill_patched = True
