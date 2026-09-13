# `deploy/aa_docker/` file inventory — real, extracted purposes

108 top-level Python files patch, extend, or glue together the ~30 installed AA apps this stack runs. Every row below is that file's own module docstring — extracted with `ast.get_docstring()`, not summarized from memory — so it stays accurate as files change. Regenerate with:

```python
import ast, pathlib
root = pathlib.Path("deploy/aa_docker")
skip = {"local.py", "celery.py", "urls.py", "wsgi.py", "settings.py", "__init__.py"}
for f in sorted(root.glob("*.py")):
    if f.name in skip: continue
    doc = ast.get_docstring(ast.parse(f.read_text(errors="replace")))
    print(f.name, "—", (doc or "(none)").strip().split(chr(10))[0])
```

Use this before touching any of these on an Indy Hub / AllianceAuth / corptools / etc. version bump — it's the fastest way to see what a package's own patches depend on before finding out the hard way.

| File | Purpose (from its own docstring) |
|---|---|
| `aadiscordbot_server_setup.py` | Ensure aa-discordbot has the configured guild in ``Servers``. |
| `aasrp_discord_setup.py` | Configure aa-srp Discord team notifications (channel ID + optional webhook). |
| `aasrp_hull_minus_platinum.py` | aa-srp payout = SDE hull base_price − Platinum insurance payout. |
| `admin_urls_refresh.py` | Rebuild Django admin URLs if they were frozen too early. |
| `buyback_contract_repair.py` | Repair duplicate buyback ContractItem rows and refresh stale notifications. |
| `buyback_contract_sync.py` | Buyback contract sync scheduling: dedupe ESI rows and stagger owner jobs. |
| `buyback_public_api.py` | Public buyback calculator API (no auth). |
| `buyback_tracking_decimal_repair.py` | Widen buyback Tracking money columns and guard absurd paste totals at runtime. |
| `buyback_webhook_repair.py` | Repair truncated buyback Discord webhook values and widen the DB column. |
| `buybackprogram_esi_compat.py` | aa-buybackprogram on django-esi 9: Token object + dict-shaped ESI rows. |
| `carbon_helper_oidc_register.py` | Register Carbon Helper as an Alliance Auth OIDC client. |
| `charlink_import_apps_patch.py` | Speed up Charlink ``import_apps()`` used by dashboard widgets and /charlink/. |
| `corp_project_discord.py` | Route CorpTools corporation project notifications to Discord by project name. |
| `corptools_access_patch.py` | CorpTools: Personnel / Director access to /audit/admin. |
| `corptools_admin_patch.py` | Patch CorpTools admin_create_tasks (interval + crontab ValidationError on django-celery-beat). |
| `corptools_asset_location.py` | Resolve CorpTools asset locations, including ships parked in corp hangars. |
| `corptools_audit_issues.py` | Human-readable CharacterAudit inactive reasons for account list tooltips. |
| `corptools_beat_schedule.py` | Ensure CorpTools Celery Beat tasks run every N minutes (default 30, not hourly). |
| `corptools_contracts_patch.py` | CorpTools: ESI contracts may omit issuer_id; ORM also requires integer issuer_* columns. |
| `corptools_corp_token.py` | Pin CorpTools / Market Manager corp ESI tasks to specific django-esi token IDs. |
| `corptools_mail_patch.py` | CorpTools: enable mail module on workers and tolerate mailing-list sender IDs. |
| `corptools_postgres_compat.py` | PostgreSQL-compatible CharacterAudit.get_oldest_qs for allianceauth-corptools on AA 5. |
| `corptools_request_perf.py` | CorpTools request-path performance: avoid GET writes, cheap auth checks, cache glances. |
| `corptools_schema_repair.py` | Add missing CorpTools audit timestamp columns on PostgreSQL. |
| `corptools_tasks_patch.py` | CorpTools: upstream typo `retires` in IntegrityError retry handler. |
| `corptools_wallet_compat.py` | CorpTools: wallet journal OpenAPI schema can lag new CCP ref_type values. |
| `csrf_cookie_cleanup.py` | Fix duplicate csrftoken cookies breaking Django CSRF checks. |
| `discordproxy_disable.py` | Disable discordnotify → discordproxy when DISCORDPROXY_HOST is unset/empty. |
| `emu_moons_beat_schedule.py` | Ensure EMU Moons / moonmining Celery Beat extras (django-celery-beat). |
| `esi_clients_compat.py` | django-esi 9 helpers: legacy ``esi.clients`` shim + OpenAPI provider factory. |
| `export_corp_assets_csv.py` | Export CorpTools corporation assets to CSV with resolved ship locations. |
| `export_corp_fittings_csv.py` | Export ship fittings for a corporation's authed members via ESI. |
| `export_corp_member_assets_csv.py` | Export CorpTools character assets for all authed members of a corporation. |
| `fix_buyback_contract_item_indent.py` | Fix IndentationError after contract-item sync patch in buybackprogram.models. |
| `freight_calculator_emu.py` | Replace stock aa-freight calculator with the EMU public quote engine UI. |
| `freight_charlink.py` | Charlink: ESI scopes for Freight contract handler (Axwell Raven / FLS). |
| `freight_charlink_hooks.py` | Alliance Auth hooks to register Freight Charlink import. |
| `freight_discord_reactions.py` | Discord status reactions for aa-freight pilot contract pings. |
| `freight_fls_setup.py` | False Logistic Services freight contract handler (Rogue Sinister). |
| `freight_menu_external.py` | Point Alliance Auth sidebar "Freight" at the public calculator. |
| `freight_public_api.py` | Public freight routes, quotes, coupons, and customer track API. |
| `freight_statistics_timeframe.py` | Timeframe filter for aa-freight /freight/statistics. |
| `hrapplications_discord.py` | Ping #hr-pings when HR Applications are submitted, claimed, approved, or rejected. |
| `indy_hub_copy_request_discord.py` | Announce new Indy Hub blueprint copy requests to Discord webhooks. |
| `indy_hub_copy_request_perf.py` | Speed up Indy Hub BP copy-request previews. |
| `indy_hub_corp_token.py` | Pin Indy Hub corporation ESI sync to django-esi token overrides (e.g. Lamaashtu #58). |
| `indy_hub_craft_material_rows_patch.py` | Harden Indy Hub craft material-row SQL unpacking. |
| `indy_hub_craft_number_locale_patch.py` | Force US number formatting on Indy Hub craft pages. |
| `indy_hub_craft_structures_patch.py` | Bound Indy Hub structure-assignment search for large production trees. |
| `indy_hub_dashboard_perf.py` | Cache + bulk-optimize Indy Hub corporation scope checks on dashboard load. |
| `indy_hub_deklein_fits_data.py` | Deklein Indy Hub structure loadouts keyed by ESI structure ID. |
| `indy_hub_deklein_import.py` | Import Deklein Indy Hub structures and apply pasted standup scan loadouts. |
| `indy_hub_django_compat.py` | Runtime fixes for Indy Hub on Alliance Auth 5 / Django 5. |
| `indy_hub_esi_system_id_compat.py` | Normalize ESI corporation structure payloads for Indy Hub sync. |
| `indy_hub_get_type_name.py` | Fix Indy Hub type-name lookups against modeltranslation. |
| `indy_hub_menu_badge_perf.py` | Indy Hub menu badge fixes: no SSO on scope checks + align request counts. |
| `indy_hub_postgres_compat.py` | PostgreSQL SQL rewrites for Indy Hub raw queries (eve_sde_itemtype.published is boolean). |
| `indy_hub_sheet_update.py` | Apply coalition spreadsheet taxes / services / rigs to Indy Hub structures. |
| `indy_hub_sheet_update_data.py` | Coalition industry structure sheet (Jul 2026) for Indy Hub tax/rig/service updates. |
| `indy_hub_slyce_structures.py` | Replace WOMP Indy Hub structures with Slyce/Deklein industry structures. |
| `indy_hub_structure_allowlist.py` | Keep Indy Hub free of Guns-R-Us / Solomon structures and other non-Deklein noise. |
| `indy_hub_structure_rigs.py` | Sync structure rigs from ESI corp assets (or aa-structures) into Indy Hub. |
| `indy_hub_synced_tax_edit.py` | Allow tax edits on ESI-synced Indy Hub structures. |
| `killtracker_dedup_compat.py` | Prevent duplicate Killtracker Discord posts on PostgreSQL/multi-worker setups. |
| `marketmanager_location_patch.py` | Runtime patch: never return an unsaved SolarSystem for unresolved locations. |
| `mediawiki_oidc_register.py` | Register MediaWiki as an Alliance Auth OIDC client. |
| `metenox_compat.py` | Runtime fixes for aa-metenox on minimal / lagging eveuniverse loads. |
| `mfg_advisor_api.py` | Public API: Industrial Advisor / Autonomous OS surfaces. |
| `mfg_divisional_api.py` | Divisional manufacturing portal API views (workbench, inventory, auctions). |
| `mfg_industry_api.py` | Public industry command-center APIs (prefs, lines, jobs, haul, appraise, scan). |
| `mfg_public_api.py` | Public JSON API for EMU Manufacturing Projects (eve-emu.com BFF). |
| `miningtaxes_auto_link.py` | Force-link Alliance Auth False Gods members into aa-miningtaxes. |
| `miningtaxes_daily_resilience.py` | Keep miningtaxes corp-moon ledgers fresh even when the character chord stalls. |
| `miningtaxes_negative_balance_patch.py` | Show overpayment as a negative balance on /miningtaxes/user_summary/<id>. |
| `miningtaxes_notify_patch.py` | Disable aa-miningtaxes Alliance Auth notifications when configured. |
| `miningtaxes_ore_tax_rates_patch.py` | Make ``OrePrices.tax_rate`` policy-derived instead of a per-row admin field. |
| `miningtaxes_structure_exclusions.py` | Corp-moon tax rules for aa-miningtaxes. |
| `miningtaxes_summary_perf.py` | Keep /miningtaxes/user_summary fast after FG auto-link. |
| `miningtaxes_unauth_miner_alert.py` | @here Discord alert when a non-Auth'ed character mines an alliance moon. |
| `miningtaxes_womp_filter.py` | Skip Guns-R-Us corp mining observer ESI sync when WOMP monitoring is disabled. |
| `moon_rental_public_api.py` | Public JSON API for moon rental auction manager (eve-emu.com /moon-rental). |
| `moonmining_discord_events.py` | Sync aa-moonmining extractions to Discord guild scheduled events (deduplicated). |
| `moonmining_janice_pricing.py` | aa-moonmining ore prices: Janice Jita reprocess *buy* instead of ESI averages. |
| `moonmining_member_ledger_import.py` | Fill moonmining Member Mining from miningtaxes ledgers when ESI observers are empty. |
| `moonmining_uploads_fix.py` | Fix aa-moonmining moons DataTables uploads category queryset. |
| `moonmining_womp_filter.py` | Skip WOMP / Guns-R-Us moonmining data when WOMP monitoring is disabled. |
| `notifications_cache_patch.py` | Fix Alliance Auth notification unread cache treating 0 as cache-miss. |
| `oidc_provider.py` | Alliance Auth OIDC provider (for YouTrack, Grafana, etc.). |
| `patch_allianceauth_providers_compat.py` | Append legacy ``ObjectNotFound`` / ``provider`` exports for AA 5.1+ community apps. |
| `patch_buyback_models.py` | One-shot image build patch for buybackprogram.models (django-esi 9). |
| `patch_buyback_notifications.py` | Fix reverse buyback notification links in aa-buybackprogram 3.x. |
| `patch_buyback_reverse_contract.py` | Reverse buyback contract status updates and completion notifications. |
| `patch_buyback_stats.py` | Keep finished (accepted) buybacks on program_stats* pages after expiry. |
| `patch_buyback_tracking_decimals.py` | Widen buyback Tracking money DecimalFields and guard absurd paste totals. |
| `patch_corptools_assets.py` | Corp asset list — stream rows instead of materializing the full queryset. |
| `repair_indy_hub_migrations.py` | Recover Indy Hub migrations on PostgreSQL when DB state lags Django migration records. |
| `securegroups_admin_bypass.py` | Allow Django admin user edits to assign Smart Groups without filter checks. |
| `securegroups_admin_patch.py` | Patch UserAdmin so HR can assign Smart Groups from Django admin. |
| `securegroups_title_sync.py` | Re-run title-based secure groups after CorpTools refreshes in-game corp titles. |
| `structures_bootstrap.py` | Optional aa-structures bootstrap (env-gated). |
| `structures_corp_token.py` | Pin aa-structures Owner ESI sync to specific django-esi tokens (private server). |
| `structures_guns_send_filter.py` | Block Guns-R-Us HR/membership aa-structures notifications at send time. |
| `structures_hr_webhook.py` | Route aa-structures HR / membership notifications to a dedicated Discord webhook. |
| `structures_webhook_policy.py` | aa-structures webhook policy for Guns-R-Us (corp 98633922). |
| `taskmonitor_patch.py` | Patch aa-taskmonitor: per-task Kill button on queued tasks admin list. |
| `top_postgres_compat.py` | PostgreSQL compatibility for aa-top (DB size query is MySQL-specific). |
| `womp_moon_monitoring.py` | WOMP moon mining watch lists — disable when alliance no longer tracks WOMP. |
| `womp_structures_bootstrap.py` | Stop aa-structures WOMP (Guns-R-Us) monitoring when moon watch is disabled. |
