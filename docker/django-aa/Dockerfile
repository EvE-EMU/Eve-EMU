FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# mysqlclient (Alliance Auth dependency) needs MariaDB client headers; PostgreSQL via psycopg2-binary wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        gcc g++ pkg-config git \
        libmariadb-dev-compat libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir "pip==26.2.1"

COPY allianceauth /opt/allianceauth
COPY deploy/aa_docker/patch_allianceauth_providers_compat.py /app/deploy/aa_docker/patch_allianceauth_providers_compat.py
RUN python /app/deploy/aa_docker/patch_allianceauth_providers_compat.py
COPY deploy/aa_docker/requirements-aa-extension-deps.txt /tmp/requirements-aa-extension-deps.txt
COPY deploy/aa_docker/requirements-aa-extension-apps.txt /tmp/requirements-aa-extension-apps.txt
RUN pip install --no-cache-dir -e /opt/allianceauth \
    -r /tmp/requirements-aa-extension-deps.txt \
    gunicorn whitenoise "psycopg2-binary>=2.9,<3" \
    && pip install --no-cache-dir -r /tmp/requirements-aa-extension-apps.txt --no-deps \
    && pip install --no-cache-dir "allianceauth-corptools==3.4.0" \
    && pip install --no-cache-dir "pip==26.2.1"

COPY deploy/aa_docker/patches/indy_hub/ /usr/local/lib/python3.12/site-packages/indy_hub/migrations/
# Craft BP CSRF: host-only vs Domain=.eve-emu.com cookie clash → 403 on save-workspace.
COPY deploy/aa_docker/patches/indy_hub_craft/js/craft_bp.js /usr/local/lib/python3.12/site-packages/indy_hub/static/indy_hub/js/craft_bp.js
COPY deploy/aa_docker/patches/indy_hub_craft/js/craft_bp_inline.js /usr/local/lib/python3.12/site-packages/indy_hub/static/indy_hub/js/craft_bp_inline.js
COPY deploy/aa_docker/patches/indy_hub_craft/js/craft_bp_project_rename.js /usr/local/lib/python3.12/site-packages/indy_hub/static/indy_hub/js/craft_bp_project_rename.js
COPY deploy/aa_docker/patches/indy_hub_craft/js/craft_bp_page.js /usr/local/lib/python3.12/site-packages/indy_hub/static/indy_hub/js/craft_bp_page.js
COPY deploy/aa_docker/patches/indy_hub_craft/templates/Craft_BP_v2.html /usr/local/lib/python3.12/site-packages/indy_hub/templates/indy_hub/industry/Craft_BP_v2.html

COPY industry_suite /app/industry_suite
COPY buyback_v2 /app/buyback_v2
COPY corp_orders /app/corp_orders
COPY standing_fleet_tracker /app/standing_fleet_tracker
COPY sde_wiki /app/sde_wiki

WORKDIR /app/site
RUN python -m allianceauth.bin.allianceauth start eve_auth . \
    && python -m allianceauth.bin.allianceauth update eve_auth

COPY deploy/aa_docker/eve_auth/celery.py /app/site/eve_auth/celery.py
COPY deploy/aa_docker/local.py /app/site/eve_auth/settings/local.py
COPY deploy/aa_docker/csrf_cookie_cleanup.py /app/deploy/aa_docker/csrf_cookie_cleanup.py
COPY deploy/aa_docker/esi_clients_compat.py /app/deploy/aa_docker/esi_clients_compat.py
COPY deploy/aa_docker/metenox_compat.py /app/deploy/aa_docker/metenox_compat.py
# Community apps still on ``esi.clients`` imports — swap to OpenAPI provider (django-esi 9).
COPY deploy/aa_docker/patches/esi_openapi_providers/killtracker/providers.py /usr/local/lib/python3.12/site-packages/killtracker/providers.py
COPY deploy/aa_docker/patches/esi_openapi_providers/standingssync/providers.py /usr/local/lib/python3.12/site-packages/standingssync/providers.py
COPY deploy/aa_docker/patches/esi_openapi_providers/moonmining/providers.py /usr/local/lib/python3.12/site-packages/moonmining/providers.py
COPY deploy/aa_docker/patches/moonmining/urls.py /usr/local/lib/python3.12/site-packages/moonmining/urls.py
COPY deploy/aa_docker/patches/moonmining/templates/moonmining/base.html /usr/local/lib/python3.12/site-packages/moonmining/templates/moonmining/base.html
COPY deploy/aa_docker/patches/esi_openapi_providers/buybackprogram/providers.py /usr/local/lib/python3.12/site-packages/buybackprogram/providers.py
COPY deploy/aa_docker/patch_buyback_models.py /app/deploy/aa_docker/patch_buyback_models.py
RUN python /app/deploy/aa_docker/patch_buyback_models.py
COPY deploy/aa_docker/patch_buyback_notifications.py /app/deploy/aa_docker/patch_buyback_notifications.py
RUN python /app/deploy/aa_docker/patch_buyback_notifications.py
COPY deploy/aa_docker/patch_buyback_reverse_contract.py /app/deploy/aa_docker/patch_buyback_reverse_contract.py
RUN python /app/deploy/aa_docker/patch_buyback_reverse_contract.py
COPY deploy/aa_docker/patch_buyback_stats.py /app/deploy/aa_docker/patch_buyback_stats.py
RUN python /app/deploy/aa_docker/patch_buyback_stats.py
COPY deploy/aa_docker/patch_buyback_tracking_decimals.py /app/deploy/aa_docker/patch_buyback_tracking_decimals.py
RUN python /app/deploy/aa_docker/patch_buyback_tracking_decimals.py
COPY deploy/aa_docker/buyback_contract_sync.py /app/deploy/aa_docker/buyback_contract_sync.py
COPY deploy/aa_docker/buyback_contract_repair.py /app/deploy/aa_docker/buyback_contract_repair.py
COPY deploy/aa_docker/buybackprogram_esi_compat.py /app/deploy/aa_docker/buybackprogram_esi_compat.py
COPY deploy/aa_docker/buyback_webhook_repair.py /app/deploy/aa_docker/buyback_webhook_repair.py
COPY deploy/aa_docker/buyback_tracking_decimal_repair.py /app/deploy/aa_docker/buyback_tracking_decimal_repair.py
# Charlink SSO callback: avoid sync miningtaxes admin stats rebuild (gunicorn timeout).
COPY deploy/aa_docker/patches/charlink/imports/miningtaxes.py /usr/local/lib/python3.12/site-packages/charlink/imports/miningtaxes.py
COPY deploy/aa_docker/patches/esi_openapi_providers/structures/providers.py /usr/local/lib/python3.12/site-packages/structures/providers.py
COPY deploy/aa_docker/patches/corptools/api/core/menu.py /usr/local/lib/python3.12/site-packages/corptools/api/core/menu.py
COPY deploy/aa_docker/patch_corptools_assets.py /app/deploy/aa_docker/patch_corptools_assets.py
RUN python /app/deploy/aa_docker/patch_corptools_assets.py
COPY deploy/aa_docker/corptools_audit_issues.py /app/deploy/aa_docker/corptools_audit_issues.py
COPY deploy/aa_docker/corptools_request_perf.py /app/deploy/aa_docker/corptools_request_perf.py
COPY deploy/aa_docker/corptools_contracts_patch.py /app/deploy/aa_docker/corptools_contracts_patch.py
COPY deploy/aa_docker/corptools_mail_patch.py /app/deploy/aa_docker/corptools_mail_patch.py
COPY deploy/aa_docker/corptools_access_patch.py /app/deploy/aa_docker/corptools_access_patch.py
COPY deploy/aa_docker/corptools_admin_patch.py /app/deploy/aa_docker/corptools_admin_patch.py
COPY deploy/aa_docker/corptools_beat_schedule.py /app/deploy/aa_docker/corptools_beat_schedule.py
COPY deploy/aa_docker/corptools_schema_repair.py /app/deploy/aa_docker/corptools_schema_repair.py
COPY deploy/aa_docker/corptools_corp_token.py /app/deploy/aa_docker/corptools_corp_token.py
COPY deploy/aa_docker/structures_corp_token.py /app/deploy/aa_docker/structures_corp_token.py
COPY deploy/aa_docker/discordproxy_disable.py /app/deploy/aa_docker/discordproxy_disable.py
COPY deploy/aa_docker/aadiscordbot_server_setup.py /app/deploy/aa_docker/aadiscordbot_server_setup.py
COPY deploy/aa_docker/structures_bootstrap.py /app/deploy/aa_docker/structures_bootstrap.py
COPY deploy/aa_docker/womp_moon_monitoring.py /app/deploy/aa_docker/womp_moon_monitoring.py
COPY deploy/aa_docker/womp_structures_bootstrap.py /app/deploy/aa_docker/womp_structures_bootstrap.py
COPY deploy/aa_docker/miningtaxes_womp_filter.py /app/deploy/aa_docker/miningtaxes_womp_filter.py
COPY deploy/aa_docker/miningtaxes_daily_resilience.py /app/deploy/aa_docker/miningtaxes_daily_resilience.py
COPY deploy/aa_docker/miningtaxes_auto_link.py /app/deploy/aa_docker/miningtaxes_auto_link.py
COPY deploy/aa_docker/miningtaxes_summary_perf.py /app/deploy/aa_docker/miningtaxes_summary_perf.py
COPY deploy/aa_docker/miningtaxes_structure_exclusions.py /app/deploy/aa_docker/miningtaxes_structure_exclusions.py
COPY deploy/aa_docker/miningtaxes_negative_balance_patch.py /app/deploy/aa_docker/miningtaxes_negative_balance_patch.py
COPY deploy/aa_docker/miningtaxes_ore_tax_rates_patch.py /app/deploy/aa_docker/miningtaxes_ore_tax_rates_patch.py
COPY deploy/aa_docker/miningtaxes_notify_patch.py /app/deploy/aa_docker/miningtaxes_notify_patch.py
COPY deploy/aa_docker/miningtaxes_unauth_miner_alert.py /app/deploy/aa_docker/miningtaxes_unauth_miner_alert.py
COPY deploy/aa_docker/moonmining_womp_filter.py /app/deploy/aa_docker/moonmining_womp_filter.py
COPY deploy/aa_docker/moonmining_uploads_fix.py /app/deploy/aa_docker/moonmining_uploads_fix.py
COPY deploy/aa_docker/moonmining_janice_pricing.py /app/deploy/aa_docker/moonmining_janice_pricing.py
COPY deploy/aa_docker/aasrp_discord_setup.py /app/deploy/aa_docker/aasrp_discord_setup.py
COPY deploy/aa_docker/hrapplications_discord.py /app/deploy/aa_docker/hrapplications_discord.py
COPY deploy/aa_docker/aasrp_hull_minus_platinum.py /app/deploy/aa_docker/aasrp_hull_minus_platinum.py
COPY deploy/aa_docker/structures_webhook_policy.py /app/deploy/aa_docker/structures_webhook_policy.py
COPY deploy/aa_docker/structures_guns_send_filter.py /app/deploy/aa_docker/structures_guns_send_filter.py
COPY deploy/aa_docker/structures_hr_webhook.py /app/deploy/aa_docker/structures_hr_webhook.py
COPY deploy/aa_docker/indy_hub_corp_token.py /app/deploy/aa_docker/indy_hub_corp_token.py
COPY deploy/aa_docker/indy_hub_django_compat.py /app/deploy/aa_docker/indy_hub_django_compat.py
COPY deploy/aa_docker/indy_hub_copy_request_discord.py /app/deploy/aa_docker/indy_hub_copy_request_discord.py
COPY deploy/aa_docker/indy_hub_postgres_compat.py /app/deploy/aa_docker/indy_hub_postgres_compat.py
COPY deploy/aa_docker/indy_hub_craft_structures_patch.py /app/deploy/aa_docker/indy_hub_craft_structures_patch.py
COPY deploy/aa_docker/indy_hub_craft_material_rows_patch.py /app/deploy/aa_docker/indy_hub_craft_material_rows_patch.py
COPY deploy/aa_docker/indy_hub_craft_number_locale_patch.py /app/deploy/aa_docker/indy_hub_craft_number_locale_patch.py
COPY deploy/aa_docker/indy_hub_dashboard_perf.py /app/deploy/aa_docker/indy_hub_dashboard_perf.py
COPY deploy/aa_docker/indy_hub_menu_badge_perf.py /app/deploy/aa_docker/indy_hub_menu_badge_perf.py
COPY deploy/aa_docker/indy_hub_get_type_name.py /app/deploy/aa_docker/indy_hub_get_type_name.py
COPY deploy/aa_docker/indy_hub_copy_request_perf.py /app/deploy/aa_docker/indy_hub_copy_request_perf.py
COPY deploy/aa_docker/indy_hub_slyce_structures.py /app/deploy/aa_docker/indy_hub_slyce_structures.py
COPY deploy/aa_docker/indy_hub_structure_rigs.py /app/deploy/aa_docker/indy_hub_structure_rigs.py
COPY deploy/aa_docker/indy_hub_structure_allowlist.py /app/deploy/aa_docker/indy_hub_structure_allowlist.py
COPY deploy/aa_docker/indy_hub_esi_system_id_compat.py /app/deploy/aa_docker/indy_hub_esi_system_id_compat.py
COPY deploy/aa_docker/indy_hub_synced_tax_edit.py /app/deploy/aa_docker/indy_hub_synced_tax_edit.py
COPY deploy/aa_docker/indy_hub_deklein_import.py /app/deploy/aa_docker/indy_hub_deklein_import.py
COPY deploy/aa_docker/indy_hub_deklein_fits_data.py /app/deploy/aa_docker/indy_hub_deklein_fits_data.py
COPY deploy/aa_docker/indy_hub_sheet_update.py /app/deploy/aa_docker/indy_hub_sheet_update.py
COPY deploy/aa_docker/indy_hub_sheet_update_data.py /app/deploy/aa_docker/indy_hub_sheet_update_data.py
COPY deploy/aa_docker/charlink_import_apps_patch.py /app/deploy/aa_docker/charlink_import_apps_patch.py
COPY deploy/aa_docker/oidc_provider.py /app/deploy/aa_docker/oidc_provider.py
COPY deploy/aa_docker/corp_project_discord.py /app/deploy/aa_docker/corp_project_discord.py
# allianceauth-oidc-provider 0.0.2 (+ patches): OIDC claims, JSON token errors, state M2M fix.
# DOT 3.4+ registration_source/cimd_expires_at skip swapped APPLICATION_MODEL — ship local 0007.
COPY deploy/aa_docker/patches/allianceauth_oidc/0007_allianceauthapplication_cimd_expires_at_and_more.py /usr/local/lib/python3.12/site-packages/allianceauth_oidc/migrations/0007_allianceauthapplication_cimd_expires_at_and_more.py
COPY deploy/aa_docker/patches/allianceauth_oidc/auth_provider.py /usr/local/lib/python3.12/site-packages/allianceauth_oidc/auth_provider.py
COPY deploy/aa_docker/patches/allianceauth_oidc/views.py /usr/local/lib/python3.12/site-packages/allianceauth_oidc/views.py
COPY deploy/aa_docker/patches/allianceauth_oidc/admin.py /usr/local/lib/python3.12/site-packages/allianceauth_oidc/admin.py
COPY deploy/aa_docker/top_postgres_compat.py /app/deploy/aa_docker/top_postgres_compat.py
# Django 5 upsert: bulk_create(update_conflicts=True) requires unique_fields (aa-sov-timer 4.2.0).
COPY deploy/aa_docker/patches/sovtimer/tasks.py /usr/local/lib/python3.12/site-packages/sovtimer/tasks.py
# aa-ledger 3.0.0 charlink hook still referenced renamed ORM fields (corporation / character).
COPY deploy/aa_docker/patches/ledger/thirdparty/charlink_hook.py /usr/local/lib/python3.12/site-packages/ledger/thirdparty/charlink_hook.py
COPY deploy/aa_docker/patches/ledger/auth_hooks.py /usr/local/lib/python3.12/site-packages/ledger/auth_hooks.py
# aa-contacts: upstream admin omits AllianceToken / CorporationToken (Charlink ESI slots).
COPY deploy/aa_docker/patches/aa_contacts/admin.py /usr/local/lib/python3.12/site-packages/aa_contacts/admin.py
# aa-metenox 2.2.1: ship upstream moons.py (old pre-2.x patch imported removed helpers).
COPY deploy/aa_docker/patches/metenox/views/moons.py /usr/local/lib/python3.12/site-packages/metenox/views/moons.py
# aa-market-manager 2.0.0: eve_sde ItemType uses group/market_group/parent_group, not item_* names.
COPY deploy/aa_docker/patches/marketmanager/models.py /usr/local/lib/python3.12/site-packages/marketmanager/models.py
COPY deploy/aa_docker/patches/marketmanager/admin.py /usr/local/lib/python3.12/site-packages/marketmanager/admin.py
COPY deploy/aa_docker/patches/marketmanager/tasks.py /usr/local/lib/python3.12/site-packages/marketmanager/tasks.py
COPY deploy/aa_docker/patches/marketmanager/cogs/marketmanager.py /usr/local/lib/python3.12/site-packages/marketmanager/cogs/marketmanager.py
COPY deploy/aa_docker/patches/marketmanager/marketbrowser-bs5.html /usr/local/lib/python3.12/site-packages/marketmanager/templates/marketmanager/marketbrowser-bs5.html
COPY deploy/aa_docker/patches/marketmanager/item_details-bs5.html /usr/local/lib/python3.12/site-packages/marketmanager/templates/marketmanager/marketbrowser/item_details-bs5.html
# aa-taskmonitor: kill single queued Celery task from Django admin
# Alliance Auth Discord: allow Django boot when DISCORD_BOT_TOKEN is unset (aadiscordbot import).
COPY deploy/aa_docker/patches/discord/core.py /opt/allianceauth/allianceauth/services/modules/discord/core.py
# django-esi 9: HTTP 304 on GetUniverseFactions broke SSO add-character (faction lookup).
COPY allianceauth/allianceauth/eveonline/providers.py /opt/allianceauth/allianceauth/eveonline/providers.py
COPY allianceauth/allianceauth/eveonline/managers.py /opt/allianceauth/allianceauth/eveonline/managers.py
COPY allianceauth/allianceauth/static/allianceauth/js/filterDropDown/filterDropDown.js /opt/allianceauth/allianceauth/static/allianceauth/js/filterDropDown/filterDropDown.js
COPY allianceauth/allianceauth/static/allianceauth/js/filterDropDown/filterDropDown.min.js /opt/allianceauth/allianceauth/static/allianceauth/js/filterDropDown/filterDropDown.min.js
COPY deploy/aa_docker/patches/taskmonitor/views.py /usr/local/lib/python3.12/site-packages/taskmonitor/views.py
COPY deploy/aa_docker/patches/taskmonitor/urls.py /usr/local/lib/python3.12/site-packages/taskmonitor/urls.py
COPY deploy/aa_docker/patches/securegroups/setup_securegroup_task.py /usr/local/lib/python3.12/site-packages/securegroups/management/commands/setup_securegroup_task.py
COPY deploy/aa_docker/patches/securegroups/signals.py /usr/local/lib/python3.12/site-packages/securegroups/signals.py
COPY deploy/aa_docker/securegroups_admin_bypass.py /app/deploy/aa_docker/securegroups_admin_bypass.py
COPY deploy/aa_docker/securegroups_admin_patch.py /app/deploy/aa_docker/securegroups_admin_patch.py
COPY deploy/aa_docker/securegroups_title_sync.py /app/deploy/aa_docker/securegroups_title_sync.py
COPY deploy/aa_docker/taskmonitor_patch.py /app/deploy/aa_docker/taskmonitor_patch.py
COPY deploy/aa_docker/repair_indy_hub_migrations.py /app/deploy/aa_docker/repair_indy_hub_migrations.py
COPY deploy/aa_docker/freight_fls_setup.py /app/deploy/aa_docker/freight_fls_setup.py
COPY deploy/aa_docker/freight_charlink.py /app/deploy/aa_docker/freight_charlink.py
COPY deploy/aa_docker/freight_charlink_hooks.py /app/deploy/aa_docker/freight_charlink_hooks.py
COPY deploy/aa_docker/extensions /app/deploy/aa_docker/extensions
COPY deploy/aa_docker/moon_rentals /app/deploy/aa_docker/moon_rentals
COPY deploy/aa_docker/emu_moons /app/deploy/aa_docker/emu_moons
COPY deploy/aa_docker/moonmining_discord_events.py /app/deploy/aa_docker/moonmining_discord_events.py
COPY deploy/aa_docker/miningtaxes_ext /app/deploy/aa_docker/miningtaxes_ext
COPY deploy/aa_docker/market_bridge /app/deploy/aa_docker/market_bridge
COPY deploy/aa_docker/buyback_public_api.py /app/deploy/aa_docker/buyback_public_api.py
COPY deploy/aa_docker/freight_public_api.py /app/deploy/aa_docker/freight_public_api.py
COPY deploy/aa_docker/freight_menu_external.py /app/deploy/aa_docker/freight_menu_external.py
COPY deploy/aa_docker/freight_bridge /app/deploy/aa_docker/freight_bridge
COPY deploy/aa_docker/moon_rental_bridge /app/deploy/aa_docker/moon_rental_bridge
COPY deploy/aa_docker/moon_rental_public_api.py /app/deploy/aa_docker/moon_rental_public_api.py
COPY deploy/aa_docker/mfg_public_api.py /app/deploy/aa_docker/mfg_public_api.py
COPY deploy/aa_docker/mfg_divisional_api.py /app/deploy/aa_docker/mfg_divisional_api.py
COPY deploy/aa_docker/mfg_industry_api.py /app/deploy/aa_docker/mfg_industry_api.py
COPY deploy/aa_docker/mfg_advisor_api.py /app/deploy/aa_docker/mfg_advisor_api.py
COPY deploy/aa_docker/mfg_projects /app/deploy/aa_docker/mfg_projects
COPY deploy/aa_docker/emu_pi /app/deploy/aa_docker/emu_pi
COPY deploy/aa_docker/discord_lookup /app/deploy/aa_docker/discord_lookup
COPY deploy/aa_docker/corptools_asset_export /app/deploy/aa_docker/corptools_asset_export
COPY deploy/aa_docker/womp_reports_download /app/deploy/aa_docker/womp_reports_download
COPY deploy/aa_docker/corp_alumni_report /app/deploy/aa_docker/corp_alumni_report
COPY deploy/aa_docker/auth_assets_report /app/deploy/aa_docker/auth_assets_report
COPY deploy/aa_docker/industry_jobs_report /app/deploy/aa_docker/industry_jobs_report
COPY deploy/aa_docker/false_gods_audit /app/deploy/aa_docker/false_gods_audit
COPY deploy/aa_docker/permissions_overview /app/deploy/aa_docker/permissions_overview
COPY deploy/aa_docker/logistics_group /app/deploy/aa_docker/logistics_group
COPY deploy/aa_docker/doctrine_contract_manager /app/deploy/aa_docker/doctrine_contract_manager
COPY deploy/aa_docker/marketing_mail /app/deploy/aa_docker/marketing_mail
COPY deploy/aa_docker/audit_comms_hub /app/deploy/aa_docker/audit_comms_hub
COPY deploy/aa_docker/winter_coalition_report /app/deploy/aa_docker/winter_coalition_report
COPY deploy/aa_docker/ffr /app/deploy/aa_docker/ffr
COPY deploy/aa_docker/rorqual_status /app/deploy/aa_docker/rorqual_status
COPY deploy/aa_docker/krab_schedule /app/deploy/aa_docker/krab_schedule
COPY deploy/aa_docker/stream_watch /app/deploy/aa_docker/stream_watch
COPY deploy/aa_docker/zomboid_service /app/deploy/aa_docker/zomboid_service
COPY deploy/aa_docker/notifications_cache_patch.py /app/deploy/aa_docker/notifications_cache_patch.py
COPY deploy/aa_docker/carbon_bridge /app/deploy/aa_docker/carbon_bridge
COPY deploy/aa_docker/admin_urls_refresh.py /app/deploy/aa_docker/admin_urls_refresh.py
COPY deploy/aa_docker/freight_discord_reactions.py /app/deploy/aa_docker/freight_discord_reactions.py
COPY deploy/aa_docker/freight_statistics_timeframe.py /app/deploy/aa_docker/freight_statistics_timeframe.py
COPY deploy/aa_docker/freight_calculator_emu.py /app/deploy/aa_docker/freight_calculator_emu.py
COPY deploy/aa_docker/corptools_asset_location.py /app/deploy/aa_docker/corptools_asset_location.py
COPY deploy/aa_docker/export_corp_assets_csv.py /app/deploy/aa_docker/export_corp_assets_csv.py
COPY deploy/aa_docker/export_corp_member_assets_csv.py /app/deploy/aa_docker/export_corp_member_assets_csv.py
COPY deploy/aa_docker/scripts/export_aa_member_audit.py /app/deploy/aa_docker/scripts/export_aa_member_audit.py
COPY deploy/aa_docker/esi_compat_app /app/deploy/aa_docker/esi_compat_app
COPY deploy/aa_docker/moonmining_member_ledger_import.py /app/deploy/aa_docker/moonmining_member_ledger_import.py
COPY deploy/aa_docker/market_seeding /app/deploy/aa_docker/market_seeding
COPY deploy/aa_docker/templates /app/deploy/aa_docker/templates
COPY deploy/aa_docker/static /app/deploy/aa_docker/static
COPY deploy/aa_docker/package_monitor_ops /app/deploy/aa_docker/package_monitor_ops
COPY deploy/aa_docker/requirements-aa-extension-apps.txt /app/deploy/aa_docker/requirements-aa-extension-apps.txt
COPY deploy/aa_docker/requirements-aa-extension-deps.txt /app/deploy/aa_docker/requirements-aa-extension-deps.txt

ENV PYTHONPATH=/app/deploy/aa_docker:/app:/app/site

RUN mkdir -p log

COPY docker/django-aa/entrypoint.py /docker-entrypoint.py
RUN chmod +x /docker-entrypoint.py

WORKDIR /app/site
EXPOSE 8080

ENTRYPOINT ["python3", "/docker-entrypoint.py"]
CMD ["celery", "-A", "eve_auth", "worker", "-l", "INFO"]
