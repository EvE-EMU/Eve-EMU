"""Celery application — Redis broker and result backend."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "emums",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.emu_moons",
        "app.tasks.rentals",
        "app.tasks.wormhole_map",
        "app.tasks.member_audit",
        "app.tasks.webhook_notifications",
        "app.tasks.service_sync",
    ],
)

celery_app.conf.update(
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "emu_moons": {"exchange": "emu_moons", "routing_key": "emu_moons"},
        "audit": {"exchange": "audit", "routing_key": "audit"},
    },
    task_routes={
        "app.tasks.emu_moons.*": {"queue": "emu_moons"},
        "app.tasks.member_audit.sync_character_audit": {"queue": "audit"},
        "app.tasks.member_audit.sync_roster_alts": {"queue": "audit"},
        "app.tasks.member_audit.rebuild_roster_interactions": {"queue": "audit"},
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "weekly-moon-invoice-billing": {
            "task": "app.tasks.emu_moons.generate_invoices",
            "schedule": crontab(hour=0, minute=0, day_of_week=1),
            "options": {"queue": "emu_moons"},
        },
        "rental-periodic-check": {
            "task": "app.tasks.rentals.run_periodic_jobs",
            "schedule": 30 * 60,
        },
        "wormhole-esi-tracking": {
            "task": "app.tasks.wormhole_map.poll_tracking_characters",
            "schedule": 5 * 60,
        },
        "coalition-member-audit": {
            "task": "app.tasks.member_audit.sync_all_characters_audit",
            "schedule": settings.audit_sync_interval_minutes * 60,
        },
        "webhook-notification-digests": {
            "task": "app.tasks.webhook_notifications.flush_webhook_notification_digests",
            "schedule": 15 * 60,
        },
        "universe-location-name-refresh": {
            "task": "app.tasks.member_audit.refresh_universe_location_names",
            "schedule": crontab(hour=3, minute=15, day_of_week=1),
        },
    },
)
