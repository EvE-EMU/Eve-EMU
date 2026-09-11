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
        if _has_app(apps, "emu_moons") and _celery_enabled("AA_EMU_MOONS_CELERY", "1"):
            # Non-private moons only; also queues miningtaxes observer refresh.
            schedule["emu_moons_sync_moonmining_reports"] = {
                "task": "emu_moons.tasks.sync_moonmining_reports",
                "schedule": crontab(minute=30, hour="*/1"),
            }
        else:
            schedule["moonmining_run_report_updates"] = {
                "task": "moonmining.tasks.run_report_updates",
                "schedule": crontab(minute=30, hour="*/1"),
            }
        schedule["moonmining_run_value_updates"] = {
            "task": "moonmining.tasks.run_calculated_properties_update",
            "schedule": crontab(minute=30, hour=3),
        }

    if _has_app(apps, "emu_moons") and _celery_enabled("AA_EMU_MOONS_CELERY", "1"):
        cfg_weekday = _env_int("AA_EMU_MOONS_INVOICE_WEEKDAY", 3)  # Thursday
        cfg_hour = _env_int("AA_EMU_MOONS_INVOICE_HOUR_UTC", 12)
        schedule["emu_moons_discover_extractions"] = {
            "task": "emu_moons.tasks.discover_extractions",
            "schedule": crontab(minute="*/15"),
        }
        schedule["emu_moons_process_invoices"] = {
            "task": "emu_moons.tasks.process_pending_invoices",
            "schedule": crontab(minute=10, hour="*/2"),
        }
        schedule["emu_moons_weekly_invoice_run"] = {
            "task": "emu_moons.tasks.weekly_invoice_run",
            "schedule": crontab(minute=0, hour=cfg_hour, day_of_week=cfg_weekday),
        }
        schedule["emu_moons_poll_wallet"] = {
            "task": "emu_moons.tasks.poll_wallet_payments",
            "schedule": crontab(minute="*/30"),
        }
        schedule["emu_moons_refresh_penalties"] = {
            "task": "emu_moons.tasks.refresh_penalties",
            "schedule": crontab(minute=0, hour=6),
        }
        schedule["emu_moons_refresh_prices"] = {
            "task": "emu_moons.tasks.refresh_ore_prices",
            "schedule": crontab(minute=0, hour="*/6"),
        }
        schedule["emu_moons_send_reminders"] = {
            "task": "emu_moons.tasks.send_reminders",
            "schedule": crontab(minute=0, hour=10),
        }

    if _has_app(apps, "moon_tsar") and _celery_enabled("AA_MOON_TSAR_CELERY"):
        schedule["moon_tsar_discover_extractions"] = {
            "task": "moon_tsar.tasks.discover_extractions",
            "schedule": crontab(minute="*/15"),
        }
        schedule["moon_tsar_sync_extraction_ledgers"] = {
            "task": "moon_tsar.tasks.sync_extraction_ledgers",
            "schedule": crontab(minute="*/30"),
        }
        schedule["moon_tsar_generate_pending_bills"] = {
            "task": "moon_tsar.tasks.generate_pending_bills",
            "schedule": crontab(minute=5, hour="*/1"),
        }
        schedule["moon_tsar_poll_tax_payments"] = {
            "task": "moon_tsar.tasks.poll_tax_payments",
            "schedule": crontab(minute="*/30"),
        }
        schedule["moon_tsar_send_bill_reminders"] = {
            "task": "moon_tsar.tasks.send_bill_reminders",
            "schedule": crontab(minute=0, hour=9),
        }
        schedule["moon_tsar_refresh_profitability"] = {
            "task": "moon_tsar.tasks.refresh_profitability_snapshots",
            "schedule": crontab(minute=0, hour=4),
        }
        schedule["moon_tsar_refresh_heatmap"] = {
            "task": "moon_tsar.tasks.refresh_heatmap",
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

    if _has_app(apps, "freight"):
        # Default 180s: 600s left new courier contracts un-pinged for up to ~10 minutes
        # (beat wait + ESI). ESI itself often takes 80–150s, so stay >= ~180s to avoid
        # QueueOnce skipping overlapping runs.
        schedule["freight_run_contracts_sync"] = {
            "task": "freight.tasks.run_contracts_sync",
            "schedule": _env_int("AA_BEAT_FREIGHT_SECONDS", 180),
        }

    if _has_app(apps, "ffr") and _celery_enabled("AA_FFR_CELERY", "1"):
        # Hourly CorpTools balance poll + FFR journal import
        schedule["ffr_poll_corp_balances"] = {
            "task": "ffr.tasks.poll_corp_balances",
            "schedule": crontab(minute=10),
        }
        # Deeper journal catch-up a few times per day
        schedule["ffr_sync_wallets"] = {
            "task": "ffr.tasks.sync_wallets",
            "schedule": crontab(minute=45, hour="*/4"),
        }
        schedule["ffr_refresh_bond_book_values"] = {
            "task": "ffr.tasks.refresh_bond_book_values",
            "schedule": crontab(minute=5, hour=4, day_of_month=1),
        }
        schedule["ffr_monthly_dividend_draft"] = {
            "task": "ffr.tasks.create_monthly_dividend_draft",
            "schedule": crontab(minute=20, hour=5, day_of_month=1),
        }
        # ffr_check_low_balances permanently disabled

    if _has_app(apps, "buybackprogram"):
        buyback_contract_minute = os.environ.get(
            "AA_BEAT_BUYBACK_CONTRACTS_MINUTE", "5,35"
        ).strip()
        schedule["buybackprogram_update_all_prices"] = {
            "task": "buybackprogram.tasks.update_all_prices",
            "schedule": crontab(minute=0, hour=0),
        }
        schedule["buybackprogram_update_all_contracts"] = {
            "task": "buybackprogram.tasks.update_all_contracts",
            "schedule": crontab(minute=buyback_contract_minute),
        }
        schedule["buybackprogram_update_program_performance"] = {
            "task": "buybackprogram.tasks.update_program_performance",
            "schedule": crontab(minute=0, hour=0),
        }
        schedule["buybackprogram_update_all_hangars"] = {
            "task": "buybackprogram.tasks.update_all_hangars",
            "schedule": crontab(minute="*/15"),
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

    if _has_app(apps, "memberaudit") and _celery_enabled("AA_MEMBERAUDIT_CELERY", "1"):
        ma_seconds = _env_int("AA_BEAT_MEMBERAUDIT_SECONDS", 3600)
        schedule["memberaudit_run_regular_updates"] = {
            "task": "memberaudit.tasks.run_regular_updates",
            "schedule": ma_seconds,
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
        # Discord/webhook supply/price/margin pings — at most once every 6 hours.
        mm_watch_hours = _env_int("AA_BEAT_MARKETMANAGER_WATCH_HOURS", 6)
        schedule["marketmanager_run_all_watch_configs"] = {
            "task": "marketmanager.tasks.run_all_watch_configs",
            "schedule": crontab(minute="0", hour=f"*/{mm_watch_hours}"),
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

    if _has_app(apps, "shop") and _celery_enabled("AA_SHOP_CELERY", "1"):
        schedule["shop_refresh_all_stock"] = {
            "task": "shop.tasks.refresh_all_stock",
            "schedule": crontab(minute=0),
        }
        schedule["shop_refresh_pct_prices"] = {
            "task": "shop.tasks.refresh_pct_prices",
            "schedule": crontab(minute=0, hour="*/6"),
        }

    if _has_app(apps, "miningtaxes") and _celery_enabled("AA_MININGTAXES_CELERY", "1"):
        # Stock aa-miningtaxes beat tasks only (no custom observer sync patches).
        if _celery_enabled("AA_MININGTAXES_AUTO_LINK_FG", "1"):
            schedule["miningtaxes_auto_link_fg"] = {
                "task": "miningtaxes_auto_link.link_false_gods_members",
                "schedule": crontab(
                    minute=_env_int("AA_BEAT_MININGTAXES_AUTO_LINK_MINUTE", 20),
                ),
            }
        schedule["miningtaxes_update_daily"] = {
            "task": "miningtaxes.tasks.update_daily",
            "schedule": crontab(
                minute=_env_int("AA_BEAT_MININGTAXES_DAILY_MINUTE", 0),
                hour=_env_int("AA_BEAT_MININGTAXES_DAILY_HOUR", 1),
            ),
        }
        if _celery_enabled("AA_MININGTAXES_UNAUTH_MINER_ALERT", "1"):
            # @here Discord ping when a non-Auth'ed character mines an alliance moon.
            schedule["miningtaxes_unauth_miner_alert"] = {
                "task": "miningtaxes_unauth_miner_alert.check_unauthorized_miners",
                "schedule": crontab(minute="*/15"),
            }
        if _celery_enabled("AA_MININGTAXES_NOTIFY_ENABLED", "1"):
            schedule["miningtaxes_notifications"] = {
                "task": "miningtaxes.tasks.notify_taxes_due",
                "schedule": crontab(
                    minute=0,
                    hour=0,
                    day_of_month=str(_env_int("AA_BEAT_MININGTAXES_NOTIFY_DAY", 2)),
                ),
            }
            schedule["miningtaxes_apply_interest"] = {
                "task": "miningtaxes.tasks.apply_interest",
                "schedule": crontab(
                    minute=0,
                    hour=0,
                    day_of_month=str(_env_int("AA_BEAT_MININGTAXES_INTEREST_DAY", 15)),
                ),
            }

    if _has_app(apps, "moon_rentals") and _celery_enabled("AA_MOON_RENTALS_CELERY", "1"):
        schedule["moon_rentals_refresh_compliance"] = {
            "task": "moon_rentals.tasks.moon_rentals_refresh_compliance",
            "schedule": crontab(
                minute=_env_int("AA_BEAT_MOON_RENTALS_REFRESH_MINUTE", 30),
                hour=_env_int("AA_BEAT_MOON_RENTALS_REFRESH_HOUR", 2),
            ),
        }
        if os.environ.get("MOON_RENTALS_DISCORD_WEBHOOK_URL", "").strip() and _celery_enabled(
            "MOON_RENTALS_DISCORD_ENABLED", "1"
        ):
            schedule["moon_rentals_weekly_discord_report"] = {
                "task": "moon_rentals.tasks.moon_rentals_weekly_discord_report",
                "schedule": crontab(
                    minute=_env_int("AA_BEAT_MOON_RENTALS_WEEKLY_MINUTE", 0),
                    hour=_env_int("AA_BEAT_MOON_RENTALS_WEEKLY_HOUR", 10),
                    day_of_week=str(_env_int("AA_BEAT_MOON_RENTALS_WEEKLY_DOW", 1)),
                ),
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

    if _has_app(apps, "structures") and _celery_enabled("AA_STRUCTURES_CELERY", "1"):
        # aa-structures checks.py requires numeric schedule (seconds), not crontab.
        structures_seconds = _env_int("AA_BEAT_STRUCTURES_SECONDS", 600)
        schedule["structures_update_all_structures"] = {
            "task": "structures.tasks.update_all_structures",
            "schedule": structures_seconds,
        }
        notif_seconds = _env_int("AA_BEAT_STRUCTURES_NOTIF_SECONDS", 300)
        schedule["structures_fetch_all_notifications"] = {
            "task": "structures.tasks.fetch_all_notifications",
            "schedule": notif_seconds,
        }

    if _has_app(apps, "esi_compat_app") and os.environ.get(
        "AA_CORP_AUTH_AUDIT_DISCORD_WEBHOOK_URL", ""
    ).strip() and _celery_enabled("AA_CORP_AUTH_AUDIT_CELERY", "1"):
        audit_hour = _env_int("AA_BEAT_CORP_AUTH_AUDIT_HOUR", 9)
        audit_minute = _env_int("AA_BEAT_CORP_AUTH_AUDIT_MINUTE", 0)
        schedule["corp_auth_audit_daily_discord"] = {
            "task": "esi_compat_app.tasks.corp_auth_audit_daily_discord",
            "schedule": crontab(minute=audit_minute, hour=audit_hour),
        }

    if _has_app(apps, "corptools"):
        try:
            from corp_project_discord import corp_project_discord_enabled

            _corp_project_discord = corp_project_discord_enabled()
        except ImportError:
            _corp_project_discord = False
        if _corp_project_discord:
            poll_seconds = _env_int("AA_CORP_PROJECT_DISCORD_POLL_SECONDS", 1800)
            schedule["industry_suite_corp_project_created_discord"] = {
                "task": "industry_suite.tasks.dispatch_corp_project_created_discord_alerts",
                "schedule": poll_seconds,
            }
            schedule["industry_suite_corp_project_completed_discord"] = {
                "task": "industry_suite.tasks.dispatch_corp_project_completed_discord_alerts",
                "schedule": poll_seconds,
            }
            daily_hour = _env_int("AA_CORP_PROJECT_DISCORD_DAILY_HOUR", 14)
            daily_minute = _env_int("AA_CORP_PROJECT_DISCORD_DAILY_MINUTE", 30)
            schedule["industry_suite_corp_project_daily_digest"] = {
                "task": "industry_suite.tasks.dispatch_corp_project_daily_digest",
                "schedule": crontab(minute=daily_minute, hour=daily_hour),
            }

    if _has_app(apps, "winter_coalition_report") and _celery_enabled("AA_WINTER_CO_CELERY", "1"):
        wc_weekday = _env_int("AA_WINTER_CO_WEEKDAY", 0)  # Monday UTC
        wc_hour = _env_int("AA_WINTER_CO_HOUR_UTC", 5)
        schedule["winter_coalition_report_weekly"] = {
            "task": "winter_coalition_report.tasks.run_weekly_report",
            "schedule": crontab(minute=15, hour=wc_hour, day_of_week=wc_weekday),
        }

    if _has_app(apps, "doctrine_contract_manager") and _celery_enabled(
        "AA_DOCTRINE_CONTRACT_MANAGER_CELERY", "1"
    ):
        dcm_minutes = _env_int("AA_DOCTRINE_CONTRACT_MANAGER_MINUTES", 30)
        schedule["doctrine_contract_manager_evaluate_all"] = {
            "task": "doctrine_contract_manager.tasks.evaluate_all_contract_rules",
            "schedule": crontab(minute=f"*/{dcm_minutes}"),
        }

    if _has_app(apps, "moon_rental_bridge") and _celery_enabled(
        "MOON_RENTAL_CELERY", "1"
    ):
        schedule["moon_rental_bridge_close_expired_auctions"] = {
            "task": "moon_rental_bridge.close_expired_auctions",
            "schedule": crontab(minute="*/5"),
        }

    if _has_app(apps, "mfg_projects") and _celery_enabled("MFG_DIVISIONAL_ENABLED", "1"):
        schedule["mfg_projects_close_expired_auctions"] = {
            "task": "mfg_projects.close_expired_auctions",
            "schedule": crontab(minute="*/5"),
        }
        schedule["mfg_projects_scan_inventory_reorder"] = {
            "task": "mfg_projects.scan_inventory_reorder",
            "schedule": crontab(minute=20),
        }

    if _has_app(apps, "emu_pi") and _celery_enabled("EMU_PI_CELERY", "1"):
        pi_minutes = _env_int("EMU_PI_SYNC_MINUTES", 15)
        schedule["emu_pi_sync_all_users"] = {
            "task": "emu_pi.sync_all_users",
            "schedule": crontab(minute=f"*/{pi_minutes}"),
        }

    if _has_app(apps, "rorqual_status") and _celery_enabled("AA_RORQUAL_CELERY", "0"):
        # Defaults off until cutover; enable with AA_RORQUAL_CELERY=1
        schedule["rorqual_evaluate_all"] = {
            "task": "rorqual.evaluate_all",
            "schedule": 60,
        }
        schedule["rorqual_project_discord"] = {
            "task": "rorqual.project_discord",
            "schedule": 60,
        }
        schedule["rorqual_scan_zkill_deklein"] = {
            "task": "rorqual.scan_zkill_deklein",
            "schedule": 120,
        }
        schedule["rorqual_sov_refresh"] = {
            "task": "rorqual.sov_refresh",
            "schedule": crontab(minute=15),
        }
        schedule["rorqual_economy_accrue"] = {
            "task": "rorqual.economy_accrue",
            "schedule": 60,
        }
        schedule["rorqual_scout_checkin_watch"] = {
            "task": "rorqual.scout_checkin_watch",
            "schedule": 60,
        }
        schedule["rorqual_fleet_timer_watch"] = {
            "task": "rorqual.fleet_timer_watch",
            "schedule": 60,
        }
        schedule["rorqual_health_alerts"] = {
            "task": "rorqual.health_alerts",
            "schedule": crontab(minute="*/5"),
        }

    if _has_app(apps, "krab_schedule") and _celery_enabled("AA_KRAB_CELERY", "1"):
        schedule["krab_post_upcoming_discord"] = {
            "task": "krab.post_upcoming_discord",
            "schedule": crontab(minute="*/15"),
        }

    # Heal CharacterAudit.active stuck False after concurrent module sync races /
    # prior is_active dual-patch bugs (recurring Trans-U / Cockhand class of issue).
    if _has_app(apps, "esi_compat_app") and _celery_enabled(
        "AA_CORPTOOLS_HEAL_STUCK_AUDITS", "1"
    ):
        heal_minutes = _env_int("AA_CORPTOOLS_HEAL_STUCK_AUDITS_MINUTES", 15)
        schedule["corptools_heal_stuck_character_audits"] = {
            "task": "esi_compat_app.heal_stuck_character_audits",
            "schedule": crontab(minute=f"*/{heal_minutes}"),
        }

    return schedule
