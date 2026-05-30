"""Wire Alliance Auth community extensions into eve_auth settings."""

from __future__ import annotations

import os

from .apps import EXTENSION_SUPPORT_APPS, extension_installed_apps
from .celerybeat import extension_celerybeat_schedule
from .settings import (
    DISCORD_SERVICE_APP,
    apply_extension_settings,
    discord_service_enabled,
)

# Still present in older deployments / manual local.py overrides — drop to stop orphan tasks.
DEPRECATED_INSTALLED_APPS: frozenset[str] = frozenset(
    {
        "blueprints",
        "memberaudit_dashboard",
        "aa_memberaudit_dashboard",
        "taxsystem",
        "aa_taxsystem",
        "srppayouts",
        "aa_srppayouts",
        "ravworks_exporter",
        "aa_ravworks_exporter",
        # Slim bundle (removed from requirements / INSTALLED_APPS — drop orphan labels)
        "killstats",
        "metenox",
        "aasrp",
        "afat",
        "skillfarm",
        "moon_tsar",
        "miningtaxes_ext",
    }
)


def configure_extensions(settings: dict) -> None:
    """Mutate a settings module dict (typically ``local.py`` globals)."""
    if os.environ.get("AA_EXTENSIONS_ENABLED", "1").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return

    if os.environ.get("AA_USE_MODELTRANSLATION", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        installed = list(settings.get("INSTALLED_APPS", []))
        if "modeltranslation" not in installed:
            settings["INSTALLED_APPS"] = ["modeltranslation"] + installed

    extra = extension_installed_apps()
    slate_apps = ["aa_theme_slate", "aa_theme_slate.theme.slate"]
    installed = [a for a in settings.get("INSTALLED_APPS", []) if a not in slate_apps]
    _esi_compat = "esi_compat_app.apps.EsiCompatConfig"
    if _esi_compat not in installed:
        installed.insert(0, _esi_compat)
    if any(a in slate_apps for a in extra):
        installed = slate_apps + installed
    for label in EXTENSION_SUPPORT_APPS:
        if label not in installed:
            installed.insert(0, label)
    for label in extra:
        if label not in installed:
            installed.append(label)
    installed = [label for label in installed if label not in DEPRECATED_INSTALLED_APPS]
    if discord_service_enabled() and DISCORD_SERVICE_APP not in installed:
        installed.append(DISCORD_SERVICE_APP)
    settings["INSTALLED_APPS"] = installed

    beat = settings.setdefault("CELERYBEAT_SCHEDULE", {})
    beat.update(extension_celerybeat_schedule(settings["INSTALLED_APPS"]))

    apply_extension_settings(settings)

    hooks_app = "extensions.hooks_apps.EveEmuHooksConfig"
    if hooks_app not in settings.get("INSTALLED_APPS", []):
        settings["INSTALLED_APPS"] = [hooks_app, *settings.get("INSTALLED_APPS", [])]
