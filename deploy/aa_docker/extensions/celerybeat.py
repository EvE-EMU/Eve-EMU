"""Celery Beat entries for community extensions (merged into CELERYBEAT_SCHEDULE)."""

from __future__ import annotations

import os

from celery.schedules import crontab


def _enabled() -> bool:
    return os.environ.get("AA_EXTENSIONS_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _has_app(installed: set[str], label: str) -> bool:
    return label in installed or any(
        entry == label or entry.startswith(f"{label}.") for entry in installed
    )


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _celery_enabled(env_key: str, default: str = "1") -> bool:
    return os.environ.get(env_key, default).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def extension_celerybeat_schedule(installed_apps: list[str] | tuple[str, ...]) -> dict:
    if not _enabled():
        return {}

    apps = set(installed_apps)
    schedule: dict = {}

    if _has_app(apps, "package_monitor"):
        schedule["package_monitor_update_distributions"] = {
            "task": "package_monitor.tasks.update_distributions",
            "schedule": crontab(minute="*/60"),
        }

    if _has_app(apps, "standingssync"):
        schedule["standingssync_run_regular_sync"] = {
            "task": "standingssync.tasks.run_regular_sync",
            "schedule": 7200,
        }

    if _has_app(apps, "structuretimers"):
        schedule["structuretimers_housekeeping"] = {
            "task": "structuretimers.tasks.housekeeping",
            "schedule": crontab(minute=0, hour=3),
        }

    if _has_app(apps, "moonmining") and _celery_enabled("AA_MOONMINING_CELERY"):
        moonmining_minutes = _env_int("AA_BEAT_MOONMINING_MINUTES", 30)
        schedule["moonmining_run_regular_updates"] = {
            "task": "moonmining.tasks.run_regular_updates",
            "schedule": crontab(minute=f"*/{moonmining_minutes}"),
        }
        schedule["moonmining_run_report_updates"] = {
            "task": "moonmining.tasks.run_report_updates",
            "schedule": crontab(minute=30, hour="*/1"),
        }
        schedule["moonmining_run_value_updates"] = {
            "task": "moonmining.tasks.run_calculated_properties_update",
            "schedule": crontab(minute=30, hour=3),
        }

    if _has_app(apps, "metenox"):
        schedule["metenox_update_prices"] = {
            "task": "metenox.tasks.update_prices",
            "schedule": crontab(minute="0", hour="*/12"),
        }
        schedule["metenox_update_moons_from_moonmining"] = {
            "task": "metenox.tasks.update_moons_from_moonmining",
            "schedule": crontab(minute="0", hour="*/3"),
        }
        schedule["metenox_update_all_holdings"] = {
            "task": "metenox.tasks.update_all_holdings",
            "schedule": crontab(minute="0", hour="*/1"),
        }
        schedule["metenox_send_daily_analytics"] = {
            "task": "metenox.tasks.send_daily_analytics",
            "schedule": crontab(minute="0", hour="5"),
        }

    if _has_app(apps, "buybackprogram"):
        schedule["buybackprogram_update_all_prices"] = {
            "task": "buybackprogram.tasks.update_all_prices",
            "schedule": crontab(minute=0, hour=0),
        }
        schedule["buybackprogram_update_all_contracts"] = {
            "task": "buybackprogram.tasks.update_all_contracts",
            "schedule": crontab(minute="*/30"),
        }
        schedule["buybackprogram_update_program_performance"] = {
            "task": "buybackprogram.tasks.update_program_performance",
            "schedule": crontab(minute=0, hour=0),
        }

    if _has_app(apps, "killtracker"):
        schedule["killtracker_run_killtracker"] = {
            "task": "killtracker.tasks.run_killtracker",
            "schedule": _env_int("AA_BEAT_KILLTRACKER_SECONDS", 300),
        }

    if _has_app(apps, "sovtimer"):
        schedule["sovtimer_run_sov_campaign_updates"] = {
            "task": "sovtimer.tasks.run_sov_campaign_updates",
            "schedule": _env_int("AA_BEAT_SOVTIMER_SECONDS", 300),
        }

    if _has_app(apps, "esistatus"):
        schedule["esistatus_update_esi_status"] = {
            "task": "esistatus.tasks.update_esi_status",
            "schedule": _env_int("AA_BEAT_ESISTATUS_SECONDS", 300),
        }

    if _has_app(apps, "alumni"):
        schedule["alumni_run_alumni_check_all"] = {
            "task": "alumni.tasks.run_alumni_check_all",
            "schedule": crontab(minute=0, hour=0, day_of_week=4),
        }
        schedule["alumni_run_update_models_subset"] = {
            "task": "alumni.tasks.update_models_subset",
            "schedule": crontab(minute="0", hour="0"),
        }

    if _has_app(apps, "skillfarm"):
        schedule["skillfarm_update_all"] = {
            "task": "skillfarm.tasks.update_all_skillfarm",
            "schedule": 1800,
        }
        schedule["skillfarm_check_notifications"] = {
            "task": "skillfarm.tasks.check_skillfarm_notifications",
            "schedule": crontab(minute=0, hour="*/24"),
        }
        schedule["skillfarm_update_all_prices"] = {
            "task": "skillfarm.tasks.update_all_prices",
            "schedule": crontab(minute=0, hour="0"),
        }

    if _has_app(apps, "ledger"):
        schedule["ledger_update_subset_characters"] = {
            "task": "ledger.tasks.update_subset_characters",
            "schedule": 1800,
        }
        schedule["ledger_update_subset_corporations"] = {
            "task": "ledger.tasks.update_subset_corporations",
            "schedule": 1800,
        }
        schedule["ledger_check_planetary_alarms"] = {
            "task": "ledger.tasks.check_planetary_alarms",
            "schedule": 10800,
        }

    if _has_app(apps, "killstats"):
        killstats_minutes = _env_int("AA_BEAT_KILLSTATS_MINUTES", 5)
        schedule["killstats_run_zkb"] = {
            "task": "killstats.tasks.run_zkb_r2z2",
            "schedule": crontab(minute=f"*/{killstats_minutes}"),
        }

    if _has_app(apps, "aa_intel_tool"):
        schedule["aa_intel_tool_housekeeping"] = {
            "task": "aa_intel_tool.tasks.housekeeping",
            "schedule": crontab(minute="0", hour="1"),
        }

    if _has_app(apps, "inactivity"):
        schedule["inactivity_check_inactivity"] = {
            "task": "inactivity.tasks.check_inactivity",
            "schedule": crontab(minute=0, hour=0),
        }

    if _has_app(apps, "aa_contacts"):
        schedule["aa_contacts_update_all_contacts"] = {
            "task": "aa_contacts.tasks.update_all_contacts",
            "schedule": crontab(minute="0"),
        }

    if _has_app(apps, "afat"):
        afat_minutes = _env_int("AA_BEAT_AFAT_MINUTES", 5)
        schedule["afat_update_esi_fatlinks"] = {
            "task": "afat.tasks.update_esi_fatlinks",
            "schedule": crontab(minute=f"*/{afat_minutes}"),
        }
        schedule["afat_logrotate"] = {
            "task": "afat.tasks.logrotate",
            "schedule": crontab(minute="0", hour="1"),
        }

    if _has_app(apps, "top"):
        top_minutes = _env_int("AA_BEAT_TOP_MINUTES", 15)
        schedule["top_update_aa_top_txt"] = {
            "task": "top.tasks.update_aa_top_txt",
            "schedule": crontab(minute=f"*/{top_minutes}"),
        }

    if _has_app(apps, "aa_skip_email"):
        schedule["aa_skip_email_fill_missing_emails"] = {
            "task": "aa_skip_email.fill_missing_emails",
            "schedule": crontab(minute=0, hour="*/6"),
        }

    if _has_app(apps, "eve_sde"):
        schedule["eve_sde_check_for_sde_updates"] = {
            "task": "eve_sde.tasks.check_for_sde_updates",
            "schedule": crontab(minute="0", hour="12"),
        }

    if _has_app(apps, "marketmanager") and _celery_enabled(
        "AA_MARKETMANAGER_CELERY", "1"
    ):
        schedule["marketmanager_fetch_public_market_orders"] = {
            "task": "marketmanager.tasks.fetch_public_market_orders",
            "schedule": crontab(minute="0", hour="*/3"),
        }
        schedule["marketmanager_fetch_all_character_orders"] = {
            "task": "marketmanager.tasks.fetch_all_character_orders",
            "schedule": crontab(minute="0", hour="*/3"),
        }
        schedule["marketmanager_fetch_all_corporation_orders"] = {
            "task": "marketmanager.tasks.fetch_all_corporation_orders",
            "schedule": crontab(minute="0", hour="*/3"),
        }
        schedule["marketmanager_fetch_all_structure_orders"] = {
            "task": "marketmanager.tasks.fetch_all_structure_orders",
            "schedule": crontab(minute="0", hour="*/3"),
        }
        schedule["marketmanager_run_all_watch_configs"] = {
            "task": "marketmanager.tasks.run_all_watch_configs",
            "schedule": crontab(minute="0", hour="*/3"),
        }
        schedule["marketmanager_garbage_collection"] = {
            "task": "marketmanager.tasks.garbage_collection",
            "schedule": crontab(minute="0", hour="0"),
        }
        schedule["marketmanager_fetch_public_structures"] = {
            "task": "marketmanager.tasks.fetch_public_structures",
            "schedule": crontab(minute="0", hour="4"),
        }
        schedule["marketmanager_update_private_structures"] = {
            "task": "marketmanager.tasks.update_private_structures",
            "schedule": crontab(minute="0", hour="5"),
        }
        schedule["marketmanager_fetch_all_corporations_structures"] = {
            "task": "marketmanager.tasks.fetch_all_corporations_structures",
            "schedule": crontab(minute="0", hour="6"),
        }
        schedule["marketmanager_update_all_type_statistics"] = {
            "task": "marketmanager.tasks.update_all_type_statistics",
            "schedule": crontab(minute="0", hour="7"),
        }
        schedule["marketmanager_update_managed_supply_configs"] = {
            "task": "marketmanager.tasks.update_managed_supply_configs",
            "schedule": crontab(minute="0", hour="2"),
        }

    if _has_app(apps, "routing"):
        schedule["routing_import_trig_data"] = {
            "task": "routing.tasks.import_trig_data",
            "schedule": crontab(minute=0, hour=4, day_of_week=0),
        }

    if _has_app(apps, "indy_hub"):
        schedule["indy_hub_sync_sde_compatibility_data"] = {
            "task": "indy_hub.tasks.sde_sync.sync_sde_compatibility_data",
            "schedule": crontab(minute=0, hour=4),
        }

    if _has_app(apps, "standing_fleet_tracker") and _celery_enabled("SFT_CELERY", "1"):
        poll_seconds = _env_int(
            "SFT_POLL_INTERVAL_SECONDS",
            _env_int("AA_BEAT_SFT_POLL_SECONDS", 300),
        )
        schedule["sft_poll_all_characters"] = {
            "task": "standing_fleet_tracker.tasks.sft_poll_all_characters",
            "schedule": poll_seconds,
        }
        schedule["sft_accrue_points"] = {
            "task": "standing_fleet_tracker.tasks.sft_accrue_points",
            "schedule": crontab(minute=5),
        }
        schedule["sft_refresh_sov_cache"] = {
            "task": "standing_fleet_tracker.tasks.sft_refresh_sov_cache",
            "schedule": crontab(minute=0, hour="*/6"),
        }
        schedule["sft_purge_fit_snapshots"] = {
            "task": "standing_fleet_tracker.tasks.sft_purge_fit_snapshots",
            "schedule": crontab(minute=30, hour=3),
        }
        schedule["sft_compute_monthly_kpis"] = {
            "task": "standing_fleet_tracker.tasks.sft_compute_monthly_kpis",
            "schedule": crontab(minute=15, hour=4, day_of_month=1),
        }

    if _has_app(apps, "corp_orders"):
        schedule["corp_orders_poll_contracts"] = {
            "task": "corp_orders.tasks.poll_active_freight_contracts",
            "schedule": _env_int("CORP_ORDERS_POLL_SECONDS", 600),
        }

    return schedule
