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

    domain = os.environ.get("DOMAIN_NAME", "").strip()
    wiki_public = os.environ.get("WIKIJS_URL", "").strip()
    if not wiki_public and domain:
        wiki_public = f"https://wiki.{domain}"
    settings.setdefault("WIKIJS_URL", wiki_public)
    settings.setdefault(
        "WIKIJS_API_URL",
        os.environ.get("WIKIJS_API_URL", "").strip() or "http://wikijs:3000",
    )
    settings.setdefault("WIKIJS_API_KEY", os.environ.get("WIKIJS_API_KEY", ""))
    settings.setdefault("WIKIJS_AADISCORDBOT_INTEGRATION", False)

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

    if _app_installed(installed, "wikijs"):
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
        # Only wire discordproxy when explicitly configured — defaulting to the
        # hostname "discordproxy" causes DNS failures when that service is absent.
        # Empty host produces DiscordProxyException ("host must not be empty … :0").
        proxy_host = os.environ.get("DISCORDPROXY_HOST", "").strip()
        if proxy_host:
            settings.setdefault("DISCORDNOTIFY_ENABLED", True)
            settings["DISCORDPROXY_HOST"] = proxy_host
            settings["DISCORDPROXY_PORT"] = int(
                os.environ.get("DISCORDPROXY_PORT", "50051")
            )
        else:
            settings["DISCORDNOTIFY_ENABLED"] = False
            settings["DISCORDPROXY_HOST"] = ""
            settings["DISCORDPROXY_PORT"] = 0

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
        "emu_moons",
        "emu_ads",
        # Winter Co ingest + emu-bot HELP APIs (UrlHook excluded_views)
        "rorqual_status",
        "krab_schedule",
        # aa-shop public storefront (browse without login)
        "storefront",
        "shop",
    ):
        if _app_installed(installed, label) or (
            label == "storefront" and _app_installed(installed, "shop")
        ):
            if label not in public_views:
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
        # Do NOT add esi-mail.send_mail.v1 to default login — only opt-in via env
        # for designated mail-sender characters (CharLink / re-auth).
        mail_scopes = [
            s.strip()
            for s in os.environ.get("AA_EMU_MOONS_MAIL_LOGIN_SCOPES", "").split()
            if s.strip()
        ]
        if mail_scopes:
            login_scopes = list(settings.get("LOGIN_TOKEN_SCOPES", ["publicData"]))
            for scope in mail_scopes:
                if scope not in login_scopes:
                    login_scopes.append(scope)
            settings["LOGIN_TOKEN_SCOPES"] = login_scopes

    if _app_installed(installed, "marketing_mail"):
        # Mail-send is tool-specific; keep it off the default new-user login consent.
        mail_scopes = [
            s.strip()
            for s in os.environ.get("AA_MARKETING_MAIL_LOGIN_SCOPES", "").split()
            if s.strip()
        ]
        if mail_scopes:
            login_scopes = list(settings.get("LOGIN_TOKEN_SCOPES", ["publicData"]))
            for scope in mail_scopes:
                if scope not in login_scopes:
                    login_scopes.append(scope)
            settings["LOGIN_TOKEN_SCOPES"] = login_scopes

    settings.setdefault(
        "AA_ESI_COMPATIBILITY_DATE",
        os.environ.get("AA_ESI_COMPATIBILITY_DATE", "2025-12-16"),
    )

    janice_key = os.environ.get("BUYBACKPROGRAM_PRICE_JANICE_API_KEY", "").strip()
    market_janice = os.environ.get("MARKET_JANICE_API_KEY", "").strip()
    if not janice_key and market_janice:
        janice_key = market_janice
    janice_method = os.environ.get("BUYBACKPROGRAM_PRICE_METHOD", "").strip()
    if janice_method:
        settings["BUYBACKPROGRAM_PRICE_METHOD"] = janice_method
    elif _app_installed(installed, "buybackprogram"):
        settings.setdefault("BUYBACKPROGRAM_PRICE_METHOD", "Janice")
    if janice_key:
        settings["BUYBACKPROGRAM_PRICE_JANICE_API_KEY"] = janice_key
        # Janice web UI (appraisal / reprocess) uses immediate/effective prices, not top-5 average.
        settings.setdefault("BUYBACKPROGRAM_PRICE_INSTANT_PRICES", True)
    if market_janice:
        settings["MARKET_JANICE_API_KEY"] = market_janice
    elif janice_key:
        settings.setdefault("MARKET_JANICE_API_KEY", janice_key)

    if _app_installed(installed, "freight"):
        op_mode = os.environ.get("FREIGHT_OPERATION_MODE", "").strip()
        if op_mode:
            settings["FREIGHT_OPERATION_MODE"] = op_mode
        else:
            settings.setdefault("FREIGHT_OPERATION_MODE", "corp_public")
        for env_key, setting_key in (
            ("FREIGHT_DISCORD_WEBHOOK_URL", "FREIGHT_DISCORD_WEBHOOK_URL"),
            ("FREIGHT_DISCORD_CUSTOMERS_WEBHOOK_URL", "FREIGHT_DISCORD_CUSTOMERS_WEBHOOK_URL"),
            ("FREIGHT_DISCORD_MENTIONS", "FREIGHT_DISCORD_MENTIONS"),
            ("FREIGHT_APP_NAME", "FREIGHT_APP_NAME"),
        ):
            val = os.environ.get(env_key, "").strip()
            if val:
                settings[setting_key] = val

    if _app_installed(installed, "moonmining"):
        # ESI EveMarketPrice averages for raw moon ore are unreliable (thin books /
        # spoof buy orders). Prefer refined goo+mineral value (aa-moonmining RM mode).
        # Opt out with MOONMINING_USE_REPROCESS_PRICING=0.
        # Material prices: Janice Jita Immediate buy by default (MOONMINING_PRICE_SOURCE).
        reprocess = os.environ.get("MOONMINING_USE_REPROCESS_PRICING", "1").strip().lower()
        settings["MOONMINING_USE_REPROCESS_PRICING"] = reprocess not in (
            "0",
            "false",
            "no",
            "off",
        )
        yield_raw = os.environ.get("MOONMINING_REPROCESSING_YIELD", "").strip()
        if yield_raw:
            try:
                settings["MOONMINING_REPROCESSING_YIELD"] = float(yield_raw)
            except ValueError:
                pass
        price_source = os.environ.get("MOONMINING_PRICE_SOURCE", "janice_buy").strip()
        if price_source:
            settings["MOONMINING_PRICE_SOURCE"] = price_source
        else:
            settings.setdefault("MOONMINING_PRICE_SOURCE", "janice_buy")
        moon_janice = os.environ.get("MOONMINING_JANICE_API_KEY", "").strip()
        if moon_janice:
            settings["MOONMINING_JANICE_API_KEY"] = moon_janice
        elif janice_key:
            settings.setdefault("MOONMINING_JANICE_API_KEY", janice_key)

    if _app_installed(installed, "miningtaxes"):
        # Stock aa-miningtaxes: Janice pricing + corp-moon-only taxes (env-overridable).
        mt_method = os.environ.get("MININGTAXES_PRICE_METHOD", "").strip()
        if mt_method:
            settings["MININGTAXES_PRICE_METHOD"] = mt_method
        elif janice_key or os.environ.get("MININGTAXES_PRICE_JANICE_API_KEY", "").strip():
            settings["MININGTAXES_PRICE_METHOD"] = "Janice"
        mt_janice = os.environ.get("MININGTAXES_PRICE_JANICE_API_KEY", "").strip() or janice_key
        if mt_janice:
            settings["MININGTAXES_PRICE_JANICE_API_KEY"] = mt_janice
        corp_div = os.environ.get("MININGTAXES_CORP_WALLET_DIVISION", "").strip()
        if corp_div.isdigit():
            settings["MININGTAXES_CORP_WALLET_DIVISION"] = int(corp_div)
        tax_corp_only = os.environ.get("MININGTAXES_TAX_ONLY_CORP_MOONS", "1").strip().lower()
        if tax_corp_only in ("0", "false", "no", "off"):
            settings["MININGTAXES_TAX_ONLY_CORP_MOONS"] = False
        else:
            settings["MININGTAXES_TAX_ONLY_CORP_MOONS"] = True
        # Package default is 0.10 (10%) for any ore type with no OrePrices row /
        # explicit tax_rate — i.e. unpriced/unlisted ore was silently taxed. Per
        # policy: unlisted ore types are not taxed at all (MININGTAXES_UNKNOWN_TAX_RATE=0).
        unknown_rate = os.environ.get("MININGTAXES_UNKNOWN_TAX_RATE", "").strip()
        if unknown_rate:
            try:
                settings["MININGTAXES_UNKNOWN_TAX_RATE"] = float(unknown_rate)
            except ValueError:
                pass

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

    if _app_installed(installed, "marketmanager"):
        mm_scopes = [
            s.strip()
            for s in os.environ.get(
                "AA_MARKET_MANAGER_LOGIN_SCOPES",
                "esi-markets.read_character_orders.v1 "
                "esi-markets.structure_markets.v1 "
                "esi-universe.read_structures.v1",
            ).split()
            if s.strip()
        ]
        login_scopes = list(settings.get("LOGIN_TOKEN_SCOPES", ["publicData"]))
        for scope in mm_scopes:
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

    if _app_installed(installed, "doctrine_contract_manager"):
        webhook = os.environ.get("DOCTRINE_CONTRACT_MANAGER_DISCORD_WEBHOOK", "").strip()
        if webhook:
            settings["DOCTRINE_CONTRACT_MANAGER_DISCORD_WEBHOOK"] = webhook
        else:
            # Fall back to Market Manager doctrine stock webhook at runtime.
            settings.setdefault("DOCTRINE_CONTRACT_MANAGER_DISCORD_WEBHOOK", "")
        settings["DOCTRINE_CONTRACT_MANAGER_FITTING_PROVIDER"] = os.environ.get(
            "DOCTRINE_CONTRACT_MANAGER_FITTING_PROVIDER",
            "doctrine_contract_manager.live_providers.aa_doctrine_fittings_provider",
        ).strip()
        settings["DOCTRINE_CONTRACT_MANAGER_CONTRACT_PROVIDER"] = os.environ.get(
            "DOCTRINE_CONTRACT_MANAGER_CONTRACT_PROVIDER",
            "doctrine_contract_manager.live_providers.aa_corptools_contract_provider",
        ).strip()
        admin_groups = os.environ.get(
            "DOCTRINE_CONTRACT_MANAGER_ADMIN_GROUPS",
            "Director,Logistics,Personnel",
        ).strip()
        settings["DOCTRINE_CONTRACT_MANAGER_ADMIN_GROUPS"] = [
            g.strip() for g in admin_groups.split(",") if g.strip()
        ]

    settings["ZOMBOID_DB_PATH"] = os.environ.get(
        "ZOMBOID_DB_PATH", "/zomboid-db/EveEmuZomboid.db"
    ).strip()
    settings["ZOMBOID_WORLD"] = os.environ.get(
        "ZOMBOID_WORLD", "EveEmuZomboid"
    ).strip() or "EveEmuZomboid"
    settings["ZOMBOID_SERVICE_URL"] = os.environ.get(
        "ZOMBOID_SERVICE_URL", "5.9.109.245:16261"
    ).strip() or "5.9.109.245:16261"

