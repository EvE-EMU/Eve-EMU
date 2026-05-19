"""Django app labels for Alliance Auth community extensions."""

from __future__ import annotations

import os

EVE_SDE_APPS: list[str] = ["eve_sde"]

EVE_UNIVERSE_APPS: list[str] = ["eveuniverse"]

SECUREGROUPS_APPS: list[str] = ["securegroups"]

# django-bootstrap-form (`{% load bootstrap %}`) — required by structures, moonmining, etc.
EXTENSION_SUPPORT_APPS: list[str] = ["bootstrapform"]

# All community apps from the eve-emu extension bundle (installed in the Docker image).
FULL_EXTENSION_APPS: list[str] = [
    *EVE_SDE_APPS,
    *EVE_UNIVERSE_APPS,
    *SECUREGROUPS_APPS,
    "package_monitor",
    "taskmonitor",
    "celeryanalytics",
    "standingssync",
    "structures",
    "structuretimers",
    "moonmining",
    "metenox",
    "buybackprogram",
    "indy_hub",
    "marketmanager",
    "killtracker",
    "killstats",
    "aa_intel_tool",
    "sovtimer",
    "routing",
    "blacklist",
    "corptools",
    "aa_contacts",
    "alumni",
    "inactivity",
    "charlink",
    "aasrp",
    "afat",
    "fleetpings",
    "fittings",
    "timezones",
    "ledger",
    "skillfarm",
    "esistatus",
    "top",
    "aa_skip_email",
    "discordnotify",
    "wikijs",
    "aa_theme_slate",
    "aa_theme_slate.theme.slate",
]

# GraphQL needs custom urlpatterns; enable with AA_EXTENSIONS_GRAPHQL=1
GRAPHQL_APPS: list[str] = [
    "allianceauth_graphql",
    "graphene_django",
    "graphql_jwt.refresh_token.apps.RefreshTokenConfig",
]


def _extensions_enabled() -> bool:
    return os.environ.get("AA_EXTENSIONS_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _graphql_enabled() -> bool:
    return os.environ.get("AA_EXTENSIONS_GRAPHQL", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def extension_installed_apps() -> list[str]:
    if not _extensions_enabled():
        return []

    apps = list(FULL_EXTENSION_APPS)
    if os.environ.get("AA_INSTALL_AADISCORDBOT", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        apps.append("aadiscordbot")
    if _graphql_enabled():
        apps.extend(GRAPHQL_APPS)

    # De-dupe preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for label in apps:
        if label not in seen:
            seen.add(label)
            ordered.append(label)
    return ordered
