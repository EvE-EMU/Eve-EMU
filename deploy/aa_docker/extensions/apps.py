"""Django app labels for Alliance Auth community extensions."""



from __future__ import annotations



import os



EVE_SDE_APPS: list[str] = ["eve_sde"]



EVE_UNIVERSE_APPS: list[str] = ["eveuniverse"]



SECUREGROUPS_APPS: list[str] = ["securegroups"]



MEMBERAUDIT_APPS: list[str] = [

    "memberaudit",

    "memberaudit_securegroups",

]



# Moon rentals + corp mining taxes (buybackprogram integration) — keep for eve-emu customizations.

MOON_MINING_APPS: list[str] = [

    "django_celery_results",

    "miningtaxes",

    "moon_rentals.apps.MoonRentalsConfig",

]



# django-bootstrap-form (`{% load bootstrap %}`) — required by structures, moonmining, etc.

EXTENSION_SUPPORT_APPS: list[str] = ["bootstrapform"]



# Disabled in the slim bundle (see docs/ALLIANCE_AUTH.md — “Retained vs removed”).

SLIM_REMOVED_APP_LABELS: frozenset[str] = frozenset(

    {

        "killstats",

        "metenox",

        "aasrp",

        "afat",

        "skillfarm",

        "moon_tsar",

        "miningtaxes_ext",

    }

)



# All community apps from the eve-emu extension bundle (installed in the Docker image).

FULL_EXTENSION_APPS: list[str] = [

    *EVE_SDE_APPS,

    *EVE_UNIVERSE_APPS,

    *SECUREGROUPS_APPS,

    *MEMBERAUDIT_APPS,

    *MOON_MINING_APPS,

    "package_monitor",

    "taskmonitor",

    "celeryanalytics",

    "standingssync",

    "structures",

    "structuretimers",

    "moonmining",

    "moonmining.rentals.apps.MoonRentalsConfig",

    "buybackprogram",

    "indy_hub",

    "marketmanager",

    "killtracker",

    "aa_intel_tool",

    "sovtimer",

    "routing",

    "blacklist",

    "corptools",

    "aa_contacts",

    "alumni",

    "inactivity",

    "charlink",

    "fleetpings",

    "fittings",

    "timezones",

    "ledger",

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



OIDC_PROVIDER_APPS: list[str] = ["oauth2_provider", "allianceauth_oidc"]





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





def _oidc_enabled() -> bool:

    return os.environ.get("AA_OIDC_ENABLED", "1").strip().lower() in (

        "1",

        "true",

        "yes",

        "on",

    )





def _aadiscordbot_enabled() -> bool:

    if os.environ.get("AA_INSTALL_AADISCORDBOT", "0").strip().lower() not in (

        "1",

        "true",

        "yes",

        "on",

    ):

        return False

    return bool(os.environ.get("DISCORD_BOT_TOKEN", "").strip())





def _is_slim_removed(entry: str) -> bool:
    return entry.split(".", 1)[0] in SLIM_REMOVED_APP_LABELS





def extension_installed_apps() -> list[str]:

    if not _extensions_enabled():

        return []



    apps = list(FULL_EXTENSION_APPS)

    if _aadiscordbot_enabled():

        apps.append("aadiscordbot")

    if _graphql_enabled():

        apps.extend(GRAPHQL_APPS)

    if _oidc_enabled():

        apps.extend(OIDC_PROVIDER_APPS)



    # De-dupe preserving order; drop slim-removed labels

    seen: set[str] = set()

    ordered: list[str] = []

    for label in apps:

        if label in seen:

            continue

        if _is_slim_removed(label):
            continue

        seen.add(label)

        ordered.append(label)

    return ordered


