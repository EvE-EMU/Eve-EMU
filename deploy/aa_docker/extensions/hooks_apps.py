"""Django AppConfig for eve-emu extension hooks (runs after apps are ready)."""

import logging

from django.apps import AppConfig


class EveEmuHooksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "extensions.hooks_apps"
    label = "eve_emu_hooks"
    verbose_name = "Eve EMU hooks"

    def ready(self) -> None:
        from extensions.character_affiliation_patch import (
            patch_eve_character_update_from_affiliation,
        )
        from extensions.corp_member_permissions import ensure_corp_member_permissions
        from extensions.discord_group_sync import (
            ensure_discord_service_state_permissions,
            register_discord_group_nickname_sync,
        )
        from extensions.oidc_state_permissions import ensure_oidc_state_permissions
        from extensions.zomboid_state_permissions import (
            ensure_zomboid_service_state_permissions,
        )
        from extensions.market_manager_scope_permissions import (
            register_market_manager_scope_permissions,
        )

        patch_eve_character_update_from_affiliation()
        register_discord_group_nickname_sync()
        ensure_discord_service_state_permissions()
        ensure_oidc_state_permissions()
        try:
            ensure_zomboid_service_state_permissions()
        except Exception:
            logging.getLogger(__name__).exception(
                "Failed to grant Zomboid service state permissions"
            )
        ensure_corp_member_permissions()
        try:
            from extensions.hr_application_permissions import (
                ensure_hr_application_permissions,
            )

            ensure_hr_application_permissions()
        except Exception:
            pass
        try:
            from hrapplications_discord import setup_hrapplications_discord

            setup_hrapplications_discord()
        except Exception:
            pass
        try:
            from extensions.false_wiki_menu import ensure_false_wiki_menu_item

            ensure_false_wiki_menu_item()
        except Exception:
            pass
        try:
            from freight_menu_external import patch_freight_menu_external

            patch_freight_menu_external()
        except Exception:
            pass
        try:
            from allianceauth.menu.core import smart_sync
            from extensions.sidebar_menu_folders import (
                ensure_sidebar_menu_folders,
                patch_reverse_buyback_menu_label,
            )

            patch_reverse_buyback_menu_label()
            smart_sync.sync_menu()
            ensure_sidebar_menu_folders()
        except Exception:
            pass
        try:
            from extensions.menu_folder_postgres import patch_menu_folder_nulls_first

            patch_menu_folder_nulls_first()
        except Exception:
            pass
        register_market_manager_scope_permissions()

        try:
            from patch_allianceauth_providers_compat import _apply_runtime_compat

            _apply_runtime_compat()
        except Exception:
            pass

        try:
            from corptools_corp_token import (
                patch_corp_token_overrides,
                patch_corptools_skip_structure_satellites,
            )

            patch_corp_token_overrides()
            patch_corptools_skip_structure_satellites()
        except Exception:
            pass

        try:
            from discordproxy_disable import patch_discordproxy_disabled

            patch_discordproxy_disabled()
        except Exception:
            pass

        try:
            from corptools_schema_repair import ensure_corptools_audit_schema

            ensure_corptools_audit_schema()
        except Exception:
            pass

        try:
            from moonmining_uploads_fix import apply_moonmining_uploads_fix

            apply_moonmining_uploads_fix()
        except ImportError:
            pass

        try:
            from moonmining_janice_pricing import apply_moonmining_janice_pricing_patch

            apply_moonmining_janice_pricing_patch()
        except ImportError:
            pass

        try:
            # Moonmining-only WOMP filter (stock aa-miningtaxes — no custom MT patches).
            from moonmining_womp_filter import apply_moonmining_womp_filter_patch
            from womp_structures_bootstrap import stop_watching_womp_structures

            apply_moonmining_womp_filter_patch()
            stop_watching_womp_structures()
        except ImportError:
            pass

        try:
            from miningtaxes_structure_exclusions import (
                apply_miningtaxes_structure_exclusion_patch,
            )

            apply_miningtaxes_structure_exclusion_patch()
        except ImportError:
            pass

        try:
            from miningtaxes_auto_link import apply_miningtaxes_auto_link

            apply_miningtaxes_auto_link()
        except ImportError:
            pass

        try:
            from miningtaxes_summary_perf import apply_miningtaxes_summary_perf_patch

            apply_miningtaxes_summary_perf_patch()
        except Exception:
            logging.getLogger(__name__).exception(
                "miningtaxes_summary_perf patch failed"
            )

        try:
            from miningtaxes_negative_balance_patch import (
                apply_miningtaxes_negative_balance_patch,
            )

            apply_miningtaxes_negative_balance_patch()
        except Exception:
            logging.getLogger(__name__).exception(
                "miningtaxes_negative_balance_patch failed"
            )

        try:
            from miningtaxes_ore_tax_rates_patch import (
                apply_miningtaxes_ore_tax_rates_patch,
            )

            apply_miningtaxes_ore_tax_rates_patch()
        except Exception:
            logging.getLogger(__name__).exception(
                "miningtaxes_ore_tax_rates_patch failed"
            )

        try:
            from miningtaxes_unauth_miner_alert import (
                apply_miningtaxes_unauth_miner_alert_patch,
            )

            apply_miningtaxes_unauth_miner_alert_patch()
        except Exception:
            logging.getLogger(__name__).exception(
                "miningtaxes_unauth_miner_alert patch failed"
            )

        try:
            from aasrp_discord_setup import setup_aasrp_discord

            setup_aasrp_discord()
        except ImportError:
            pass

        try:
            from aasrp_hull_minus_platinum import (
                apply_aasrp_hull_minus_platinum_patch,
                backfill_pending_payouts,
            )

            apply_aasrp_hull_minus_platinum_patch()
            backfill_pending_payouts()
        except Exception:
            pass

        try:
            from aadiscordbot_server_setup import ensure_aadiscordbot_server

            ensure_aadiscordbot_server()
        except Exception:
            pass

        try:
            from structures_guns_send_filter import (
                apply_structures_guns_send_filter_patch,
                maybe_purge_guns_r_us_hr_backlog,
            )
            from structures_webhook_policy import maybe_sync_guns_r_us_webhook_policy

            apply_structures_guns_send_filter_patch()
            maybe_sync_guns_r_us_webhook_policy()
            maybe_purge_guns_r_us_hr_backlog()
        except ImportError:
            pass

        try:
            from indy_hub_postgres_compat import patch_indy_hub_for_postgresql

            patch_indy_hub_for_postgresql()
        except Exception:
            pass

        try:
            from marketmanager_location_patch import patch_marketmanager_location_resolver

            patch_marketmanager_location_resolver()
        except Exception:
            pass

        try:
            from moonmining_member_ledger_import import patch_moonmining_report_updates

            patch_moonmining_report_updates()
        except Exception:
            pass

        try:
            from django.apps import apps as django_apps

            if not django_apps.is_installed("emu_moons"):
                from django_celery_beat.models import PeriodicTask

                disabled = PeriodicTask.objects.filter(
                    task__startswith="emu_moons."
                ).filter(enabled=True).update(enabled=False)
                if disabled:
                    import logging

                    logging.getLogger(__name__).info(
                        "Disabled %s orphan emu_moons PeriodicTask row(s)", disabled
                    )
        except Exception:
            pass

        try:
            from indy_hub_craft_structures_patch import patch_indy_hub_craft_structures

            patch_indy_hub_craft_structures()
        except Exception:
            pass

        try:
            from indy_hub_craft_material_rows_patch import (
                patch_indy_hub_craft_material_rows,
            )

            patch_indy_hub_craft_material_rows()
        except Exception:
            pass

        try:
            from indy_hub_craft_number_locale_patch import (
                patch_indy_hub_craft_number_locale,
            )

            patch_indy_hub_craft_number_locale()
        except Exception:
            pass

        try:
            from django.core.cache import cache

            from indy_hub_structure_allowlist import (
                patch_indy_hub_structure_allowlist,
                purge_disallowed_indy_structures,
            )

            patch_indy_hub_structure_allowlist()
            # Full-table structure purge on every gunicorn/celery ready() is expensive;
            # run at most once per hour across workers.
            if cache.add("indy_hub:structure_purge:lock", 1, timeout=3600):
                purge_disallowed_indy_structures()
        except Exception:
            pass

        try:
            from indy_hub_get_type_name import patch_indy_hub_get_type_name

            patch_indy_hub_get_type_name()
        except Exception:
            pass

        try:
            from indy_hub_dashboard_perf import patch_indy_hub_dashboard_perf

            patch_indy_hub_dashboard_perf()
        except Exception:
            pass

        try:
            from indy_hub_menu_badge_perf import patch_indy_hub_menu_badge_perf

            patch_indy_hub_menu_badge_perf()
        except Exception:
            pass

        try:
            from indy_hub_copy_request_perf import patch_indy_hub_copy_request_perf

            patch_indy_hub_copy_request_perf()
        except Exception:
            pass

        try:
            from indy_hub_esi_system_id_compat import (
                patch_indy_hub_esi_system_id_compat,
            )

            patch_indy_hub_esi_system_id_compat()
        except Exception:
            pass

        try:
            from indy_hub_synced_tax_edit import patch_indy_hub_synced_tax_edit

            patch_indy_hub_synced_tax_edit()
        except Exception:
            pass

        try:
            from metenox_compat import patch_metenox_for_runtime

            patch_metenox_for_runtime()
        except Exception:
            pass

        try:
            from charlink_import_apps_patch import patch_charlink_import_apps

            patch_charlink_import_apps()
        except Exception:
            pass

        try:
            from buyback_webhook_repair import ensure_buyback_webhook_urls

            ensure_buyback_webhook_urls()
        except Exception:
            pass

        try:
            from buyback_tracking_decimal_repair import ensure_buyback_tracking_decimals

            ensure_buyback_tracking_decimals()
        except Exception:
            pass

        try:
            from buyback_contract_repair import maybe_repair_duplicate_contract_items

            maybe_repair_duplicate_contract_items()
        except Exception:
            pass

        try:
            from extensions.wikijs_email_sync import patch_wikijs_email_sync
            from extensions.wikijs_member_edit_patch import patch_wikijs_member_edit
            from extensions.wikijs_service_patch import patch_wikijs_service_views

            patch_wikijs_email_sync()
            patch_wikijs_member_edit()
            patch_wikijs_service_views()
        except Exception:
            pass

        try:
            from freight_fls_setup import ensure_false_logistics_freight_handler

            ensure_false_logistics_freight_handler()
        except Exception:
            pass

        try:
            import freight_charlink_hooks  # noqa: F401 — registers Charlink freight scopes
        except ImportError:
            pass

        try:
            from corptools_contracts_patch import patch_corptools_contract_from_esi

            patch_corptools_contract_from_esi()
        except ImportError:
            pass

        try:
            from corptools_mail_patch import patch_corptools_mail

            patch_corptools_mail()
        except ImportError:
            pass

        try:
            from corptools_admin_patch import patch_corptools_admin_create_tasks

            patch_corptools_admin_create_tasks()
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "corptools_admin_patch: failed to apply"
            )

        try:
            from corptools_access_patch import patch_corptools_access

            patch_corptools_access()
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "corptools_access_patch: failed to apply"
            )

        try:
            from corptools_beat_schedule import apply_corptools_beat_schedule

            apply_corptools_beat_schedule()
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "corptools_beat_schedule: failed to apply"
            )

        try:
            from corptools_request_perf import patch_corptools_request_perf

            patch_corptools_request_perf()
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "corptools_request_perf: failed to apply"
            )

        try:
            from securegroups_admin_patch import patch_user_admin_securegroups

            patch_user_admin_securegroups()
        except ImportError:
            pass

        try:
            from securegroups_title_sync import apply_securegroups_title_sync_patch

            apply_securegroups_title_sync_patch()
        except ImportError:
            pass

        # Safety net: rebuild admin URLs on first request if they were frozen early.
        try:
            from django.core.signals import request_started

            from admin_urls_refresh import refresh_admin_site_urls

            def _refresh_admin_urls_once(**_kwargs):
                try:
                    refresh_admin_site_urls()
                finally:
                    request_started.disconnect(_refresh_admin_urls_once)

            request_started.connect(_refresh_admin_urls_once, weak=False)
        except Exception:
            pass
