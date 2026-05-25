"""Celery tasks for industry_suite (eve-emu Alliance Auth extensions)."""

from __future__ import annotations

from celery import shared_task


@shared_task(name="industry_suite.tasks.dispatch_corp_project_created_discord_alerts")
def dispatch_corp_project_created_discord_alerts() -> dict:
    from corp_project_discord import process_corp_project_created_alerts

    return process_corp_project_created_alerts()


@shared_task(name="industry_suite.tasks.dispatch_corp_project_completed_discord_alerts")
def dispatch_corp_project_completed_discord_alerts() -> dict:
    from corp_project_discord import process_corp_project_completed_alerts

    return process_corp_project_completed_alerts()


@shared_task(name="industry_suite.tasks.dispatch_corp_project_daily_digest")
def dispatch_corp_project_daily_digest() -> dict:
    from corp_project_discord import post_daily_outstanding_corp_project_digest

    return post_daily_outstanding_corp_project_digest()


@shared_task(name="industry_suite.tasks.dispatch_corp_project_discord_alerts")
def dispatch_corp_project_discord_alerts() -> dict:
    """Legacy combined task (created + completed). Celery beat uses split tasks."""
    from corp_project_discord import process_corp_project_discord_alerts

    return process_corp_project_discord_alerts()
