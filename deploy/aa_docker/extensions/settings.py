"""Optional Django settings for community extensions."""

from __future__ import annotations

import os


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


def apply_extension_settings(settings: dict) -> None:
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
        settings["DEFAULT_THEME"] = (
            "aa_theme_slate.theme.slate.auth_hooks.AaSlateThemeHook"
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
    for label in ("timezones", "sovtimer", "esistatus", "aa_intel_tool", "buyback_v2"):
        if label in installed and label not in public_views:
            public_views.append(label)
    if public_views:
        settings["APPS_WITH_PUBLIC_VIEWS"] = public_views

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

    if "corptools" in installed:
        ct_scopes = [
            s.strip()
            for s in os.environ.get(
                "AA_CORPTOOLS_LOGIN_SCOPES",
                "esi-characters.read_titles.v1 "
                "esi-characters.read_corporation_roles.v1",
            ).split()
            if s.strip()
        ]
        login_scopes = list(settings.get("LOGIN_TOKEN_SCOPES", ["publicData"]))
        for scope in ct_scopes:
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
