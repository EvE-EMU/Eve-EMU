"""Optional Django settings for community extensions."""

from __future__ import annotations

import os

# Alliance Auth built-in Services → Discord (OAuth link + role sync).
DISCORD_SERVICE_APP = "allianceauth.services.modules.discord"


def discord_service_enabled() -> bool:
    """True when corp Discord service should load (bot token + guild id in env)."""
    if os.environ.get("AA_DISCORD_SERVICE_ENABLED", "").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return False
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    guild = os.environ.get("DISCORD_GUILD_ID", "").strip()
    return bool(token and guild)


def _app_installed(installed: set[str], label: str) -> bool:
    """True if *label* is in INSTALLED_APPS (short name or AppConfig path)."""
    return label in installed or any(
        entry == label or entry.startswith(f"{label}.") for entry in installed
    )


def _prepend_template_dir(settings: dict, directory: str) -> None:
    templates = settings.get("TEMPLATES")
    if not templates or not isinstance(templates, list) or not templates:
        return
    backend = templates[0]
    dirs = list(backend.get("DIRS", []))
    if directory not in dirs:
        backend["DIRS"] = [directory, *dirs]
        settings["TEMPLATES"] = templates


def _apply_discord_settings(settings: dict) -> None:
    """Map root `.env` DISCORD_* into Django settings for Alliance Auth's Discord service."""
    site_url = str(settings.get("SITE_URL", "")).rstrip("/")
    for key in (
        "DISCORD_BOT_TOKEN",
        "DISCORD_GUILD_ID",
        "DISCORD_APP_ID",
        "DISCORD_APP_SECRET",
        "DISCORD_CALLBACK_URL",
    ):
        val = os.environ.get(key, "").strip()
        if val:
            settings[key] = val
    if site_url and not str(settings.get("DISCORD_CALLBACK_URL", "")).strip():
        settings.setdefault("DISCORD_CALLBACK_URL", f"{site_url}/discord/callback/")
    sync = os.environ.get("DISCORD_SYNC_NAMES", "1").strip()
    if sync:
        settings["DISCORD_SYNC_NAMES"] = sync.lower() in ("1", "true", "yes", "on")
    else:
        settings.setdefault("DISCORD_SYNC_NAMES", True)
    admin_channels = os.environ.get("DISCORD_ADMIN_BOT_CHANNELS", "").strip()
    if admin_channels:
        settings["ADMIN_DISCORD_BOT_CHANNELS"] = [
            int(x.strip()) for x in admin_channels.split(",") if x.strip().isdigit()
        ]
    else:
        settings.setdefault("ADMIN_DISCORD_BOT_CHANNELS", [])

    daily_tz = os.environ.get(
        "AA_CORP_PROJECT_DISCORD_DAILY_TZ", "America/New_York"
    ).strip()
    if daily_tz and os.environ.get("AA_CORP_PROJECT_DISCORD_ENABLED", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    ):
        settings.setdefault("CELERY_TIMEZONE", daily_tz)


def apply_extension_settings(settings: dict) -> None:
    _apply_discord_settings(settings)

    _aa_docker_templates = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "templates")
    )
    if os.path.isdir(_aa_docker_templates):
        _prepend_template_dir(settings, _aa_docker_templates)

    installed = set(settings.get("INSTALLED_APPS", []))

    if _app_installed(installed, "taskmonitor"):
        settings["TASKMONITOR_ENABLED"] = os.environ.get(
            "AA_TASKMONITOR_ENABLED", "1"
        ).strip().lower() in ("1", "true", "yes", "on")

    if "eve_sde" in installed:
        settings["ESDE_TASK_SPLIT"] = os.environ.get("AA_ESDE_TASK_SPLIT", "1").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    if "aa_theme_slate" in installed:
        theme_choice = os.environ.get("AA_DEFAULT_THEME", "flatly").strip().lower()
        if theme_choice == "slate":
            settings["DEFAULT_THEME"] = (
                "aa_theme_slate.theme.slate.auth_hooks.AaSlateThemeHook"
            )
        else:
            settings["DEFAULT_THEME"] = (
                "allianceauth.theme.flatly.auth_hooks.FlatlyThemeHook"
            )

    if "wikijs" in installed:
        domain = os.environ.get("DOMAIN_NAME", "").strip()
        wiki_public = os.environ.get("WIKIJS_URL", "").strip()
        if not wiki_public and domain:
            wiki_public = f"https://wiki.{domain}"
        wiki_api = os.environ.get("WIKIJS_API_URL", "").strip() or "http://wikijs:3000"
        settings.setdefault("WIKIJS_URL", wiki_public)
        settings.setdefault("WIKIJS_API_KEY", os.environ.get("WIKIJS_API_KEY", ""))
        settings.setdefault("WIKIJS_API_URL", wiki_api)
        settings.setdefault("WIKIJS_AADISCORDBOT_INTEGRATION", False)

    if "discordnotify" in installed:
        settings.setdefault("DISCORDNOTIFY_ENABLED", True)
        settings.setdefault(
            "DISCORDPROXY_HOST",
            os.environ.get("DISCORDPROXY_HOST", "discordproxy"),
        )
        settings.setdefault(
            "DISCORDPROXY_PORT",
            int(os.environ.get("DISCORDPROXY_PORT", "50051")),
        )

    if "aa_skip_email" in installed:
        backends = list(settings.get("AUTHENTICATION_BACKENDS", []))
        skip_backend = "aa_skip_email.authentication.backends.SkipEmailBackend"
        filtered = [
            b for b in backends if b != "allianceauth.authentication.backends.StateBackend"
        ]
        if skip_backend not in filtered:
            filtered.insert(0, skip_backend)
        settings["AUTHENTICATION_BACKENDS"] = filtered
        settings.setdefault("AA_SKIP_EMAIL_DOMAIN", "no-email.invalid")

    if os.environ.get("AA_EXTENSIONS_GRAPHQL", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        from datetime import timedelta

        settings.setdefault(
            "GRAPHENE",
            {
                "SCHEMA": "allianceauth_graphql.schema.schema",
                "MIDDLEWARE": ["graphql_jwt.middleware.JSONWebTokenMiddleware"],
            },
        )
        backends = list(settings.get("AUTHENTICATION_BACKENDS", []))
        if "graphql_jwt.backends.JSONWebTokenBackend" not in backends:
            backends.append("graphql_jwt.backends.JSONWebTokenBackend")
        settings["AUTHENTICATION_BACKENDS"] = backends
        settings.setdefault(
            "GRAPHQL_JWT",
            {
                "JWT_VERIFY_EXPIRATION": True,
                "JWT_LONG_RUNNING_REFRESH_TOKEN": True,
                "JWT_EXPIRATION_DELTA": timedelta(days=1),
                "JWT_REFRESH_EXPIRATION_DELTA": timedelta(days=7),
            },
        )

    public_views = list(settings.get("APPS_WITH_PUBLIC_VIEWS", []))
    for label in (
        "timezones",
        "sovtimer",
        "esistatus",
        "aa_intel_tool",
        "buyback_v2",
        "emu_moons",
    ):
        if label in installed and label not in public_views:
            public_views.append(label)
    if public_views:
        settings["APPS_WITH_PUBLIC_VIEWS"] = public_views

    if _app_installed(installed, "emu_moons"):
        templates = settings.get("TEMPLATES")
        if templates and isinstance(templates, list) and templates:
            ctx_procs = list(templates[0].get("OPTIONS", {}).get("context_processors", []))
            proc = "emu_moons.context_processors.emu_moons_nav"
            if proc not in ctx_procs:
                ctx_procs.append(proc)
                templates[0].setdefault("OPTIONS", {})["context_processors"] = ctx_procs
                settings["TEMPLATES"] = templates

    if "buyback_v2" in installed:
        templates = settings.get("TEMPLATES")
        if templates and isinstance(templates, list) and templates:
            ctx_procs = list(templates[0].get("OPTIONS", {}).get("context_processors", []))
            proc = "buyback_v2.context_processors.buyback_pricing_tier"
            if proc not in ctx_procs:
                ctx_procs.append(proc)
                templates[0].setdefault("OPTIONS", {})["context_processors"] = ctx_procs
                settings["TEMPLATES"] = templates

    settings.setdefault(
        "AA_ESI_COMPATIBILITY_DATE",
        os.environ.get("AA_ESI_COMPATIBILITY_DATE", "2025-12-16"),
    )

    janice_key = os.environ.get("BUYBACKPROGRAM_PRICE_JANICE_API_KEY", "").strip()
    janice_method = os.environ.get("BUYBACKPROGRAM_PRICE_METHOD", "").strip()
    if janice_method:
        settings["BUYBACKPROGRAM_PRICE_METHOD"] = janice_method
    elif _app_installed(installed, "buyback_v2") and _app_installed(
        installed, "buybackprogram"
    ):
        settings.setdefault("BUYBACKPROGRAM_PRICE_METHOD", "Janice")
    if janice_key:
        settings["BUYBACKPROGRAM_PRICE_JANICE_API_KEY"] = janice_key

    if _app_installed(installed, "miningtaxes"):
        # Optional overrides only — otherwise aa-miningtaxes app_settings defaults apply.
        mt_method = os.environ.get("MININGTAXES_PRICE_METHOD", "").strip()
        if mt_method:
            settings["MININGTAXES_PRICE_METHOD"] = mt_method
        mt_janice = os.environ.get("MININGTAXES_PRICE_JANICE_API_KEY", "").strip() or janice_key
        if mt_janice:
            settings["MININGTAXES_PRICE_JANICE_API_KEY"] = mt_janice
        corp_div = os.environ.get("MININGTAXES_CORP_WALLET_DIVISION", "").strip()
        if corp_div.isdigit():
            settings["MININGTAXES_CORP_WALLET_DIVISION"] = int(corp_div)
        tax_corp_only = os.environ.get("MININGTAXES_TAX_ONLY_CORP_MOONS", "").strip().lower()
        if tax_corp_only in ("0", "false", "no", "off"):
            settings["MININGTAXES_TAX_ONLY_CORP_MOONS"] = False
        elif tax_corp_only in ("1", "true", "yes", "on"):
            settings["MININGTAXES_TAX_ONLY_CORP_MOONS"] = True
        elif _app_installed(installed, "emu_moons"):
            # EMU Moons invoices from corp observer logs; personal ledger is opt-in fallback only.
            settings["MININGTAXES_TAX_ONLY_CORP_MOONS"] = False

    if _app_installed(installed, "moon_rentals"):
        webhook = os.environ.get("MOON_RENTALS_DISCORD_WEBHOOK_URL", "").strip()
        if webhook:
            settings["MOON_RENTALS_DISCORD_WEBHOOK_URL"] = webhook

    if os.environ.get("AA_OIDC_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        try:
            from oidc_provider import apply_oidc_settings

            apply_oidc_settings(settings)
        except Exception:
            pass

    if _app_installed(installed, "corptools"):
        settings["CT_CHAR_MAIL_MODULE"] = os.environ.get(
            "AA_CORPTOOLS_MAIL_MODULE", "1"
        ).strip().lower() in ("1", "true", "yes", "on")
        ct_scopes = [
            s.strip()
            for s in os.environ.get(
                "AA_CORPTOOLS_LOGIN_SCOPES",
                "esi-characters.read_titles.v1 "
                "esi-characters.read_corporation_roles.v1 "
                "esi-corporations.read_projects.v1 "
                "esi-mail.read_mail.v1",
            ).split()
            if s.strip()
        ]
        login_scopes = list(settings.get("LOGIN_TOKEN_SCOPES", ["publicData"]))
        for scope in ct_scopes:
            if scope not in login_scopes:
                login_scopes.append(scope)
        settings["LOGIN_TOKEN_SCOPES"] = login_scopes

    if _app_installed(installed, "industry_suite") and os.environ.get(
        "AA_CORP_PROJECT_DISCORD_ENABLED", "1"
    ).strip().lower() not in ("0", "false", "no", "off"):
        cp_scopes = [
            s.strip()
            for s in os.environ.get(
                "AA_CORP_PROJECT_DISCORD_LOGIN_SCOPES",
                "esi-corporations.read_projects.v1",
            ).split()
            if s.strip()
        ]
        login_scopes = list(settings.get("LOGIN_TOKEN_SCOPES", ["publicData"]))
        for scope in cp_scopes:
            if scope not in login_scopes:
                login_scopes.append(scope)
        settings["LOGIN_TOKEN_SCOPES"] = login_scopes

    if any(label == "standing_fleet_tracker" or label.startswith("standing_fleet_tracker.") for label in installed):
        sft_scopes = [
            s.strip()
            for s in os.environ.get(
                "SFT_REQUIRED_SCOPES",
                "esi-fleets.read_fleet.v1 esi-location.read_location.v1 "
                "esi-location.read_ship_type.v1 esi-assets.read_assets.v1 "
                "esi-killmails.read_killmails.v1",
            ).split()
            if s.strip()
        ]
        login_scopes = list(settings.get("LOGIN_TOKEN_SCOPES", ["publicData"]))
        for scope in sft_scopes:
            if scope not in login_scopes:
                login_scopes.append(scope)
        settings["LOGIN_TOKEN_SCOPES"] = login_scopes
