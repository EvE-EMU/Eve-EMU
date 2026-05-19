"""django-esi 9 helpers: legacy ``esi.clients`` shim + OpenAPI provider factory."""

from __future__ import annotations

import os
import re
import sys
import types
from typing import Any


# django-esi 9 refuses empty tags+operations when DEBUG=False (RAM limits).
# Legacy addons omit filtering; listing all root OpenAPI tags matches full-client behaviour.
# Source: ``tags`` array from https://esi.evetech.net/meta/openapi.json (X-Compatibility-Date).
_ESI_OPENAPI_ALL_TAGS: tuple[str, ...] = (
    "Alliance",
    "Assets",
    "Calendar",
    "Character",
    "Clones",
    "Contacts",
    "Contracts",
    "Corporation",
    "Corporation Projects",
    "Dogma",
    "Faction Warfare",
    "Fittings",
    "Fleets",
    "Freelance Jobs",
    "Incursions",
    "Industry",
    "Insurance",
    "Killmails",
    "Location",
    "Loyalty",
    "Mail",
    "Market",
    "Meta",
    "Planetary Interaction",
    "Routes",
    "Search",
    "Skills",
    "Sovereignty",
    "Status",
    "Universe",
    "User Interface",
    "Wallet",
    "Wars",
)


def _effective_tags_and_operations(
    tags: list[str] | None, operations: list[str] | None
) -> tuple[list[str], list[str]]:
    t = [] if tags is None else list(tags)
    o = [] if operations is None else list(operations)
    if not t and not o:
        return list(_ESI_OPENAPI_ALL_TAGS), o
    return t, o


def _default_compatibility_date() -> str:
    return os.environ.get("AA_ESI_COMPATIBILITY_DATE", "2025-12-16").strip()


def _parse_app_info_text(app_info_text: str) -> tuple[str, str]:
    text = (app_info_text or "").strip()
    match = re.match(r"(.+?)\s+v(.+)$", text, re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    if text:
        return text, "0.0.0"
    return "AaExtension", "0.0.0"


class LegacyEsiClientProvider:
    """Accepts legacy ``app_info_text=`` and delegates to ``ESIClientProvider``."""

    def __init__(
        self,
        app_info_text: str = "",
        *,
        compatibility_date: str | None = None,
        operations: list[str] | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs.pop("app_info_text", None)
        parsed_name, parsed_version = _parse_app_info_text(app_info_text)
        ua_appname = kwargs.pop("ua_appname", parsed_name)
        ua_version = kwargs.pop("ua_version", parsed_version)
        from esi.openapi_clients import ESIClientProvider

        eff_tags, eff_ops = _effective_tags_and_operations(tags, operations)
        self._provider = ESIClientProvider(
            compatibility_date=compatibility_date or _default_compatibility_date(),
            ua_appname=ua_appname,
            ua_version=ua_version,
            operations=eff_ops,
            tags=eff_tags,
            **kwargs,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provider, name)


def openapi_esi_provider_from_app_info_text(
    app_info_text: str = "",
    *,
    compatibility_date: str | None = None,
    operations: list[str] | None = None,
    tags: list[str] | None = None,
    **kwargs: Any,
) -> Any:
    """django-esi 9 ``ESIClientProvider`` using legacy ``app_info_text`` UA strings."""
    from esi.openapi_clients import ESIClientProvider

    kwargs.pop("app_info_text", None)
    parsed_name, parsed_version = _parse_app_info_text(app_info_text)
    ua_appname = kwargs.pop("ua_appname", parsed_name)
    ua_version = kwargs.pop("ua_version", parsed_version)
    eff_tags, eff_ops = _effective_tags_and_operations(tags, operations)
    return ESIClientProvider(
        compatibility_date=compatibility_date or _default_compatibility_date(),
        ua_appname=ua_appname,
        ua_version=ua_version,
        operations=eff_ops,
        tags=eff_tags,
        **kwargs,
    )


def _legacy_snake_to_pascal_operation(snake: str) -> str:
    """Map legacy django-esi 8 operation names to django-esi 9 PascalCase ids."""
    if not snake or "_" not in snake:
        return snake
    return "".join(part.capitalize() for part in snake.split("_") if part)


def _patch_esitag_legacy_operation_names() -> None:
    """Allow ``tag.get_foo_bar()`` calls used by aa-moonmining and other extensions."""
    from esi.openapi_clients import ESITag, ESITagAsync, EsiOperation, EsiOperationAsync

    if getattr(ESITag, "_eve_emu_legacy_snake_patch", False):
        return

    def _resolve_operation_key(tag: ESITag, name: str) -> str | None:
        if name in tag._operations:
            return name
        pascal = _legacy_snake_to_pascal_operation(name)
        if pascal in tag._operations:
            return pascal
        return None

    def esitag_getattr(self: ESITag, name: str) -> EsiOperation:
        key = _resolve_operation_key(self, name)
        if key is not None:
            return EsiOperation(self._operations[key], self.api)
        raise AttributeError(
            f"Operation '{name}' not found in tag '{self._oi}'. "
            f"Available operations: {', '.join(sorted(self._operations.keys()))}"
        )

    def esitag_async_getattr(self: ESITagAsync, name: str) -> EsiOperationAsync:
        key = _resolve_operation_key(self, name)
        if key is not None:
            return EsiOperationAsync(self._operations[key], self.api)
        raise AttributeError(
            f"Operation '{name}' not found in tag '{self._oi}'. "
            f"Available operations: {', '.join(sorted(self._operations.keys()))}"
        )

    ESITag.__getattr__ = esitag_getattr  # type: ignore[method-assign]
    ESITagAsync.__getattr__ = esitag_async_getattr  # type: ignore[method-assign]
    ESITag._eve_emu_legacy_snake_patch = True


def install_esi_clients_shim() -> None:
    if "esi.clients" in sys.modules:
        return

    module = types.ModuleType("esi.clients")
    module.EsiClientProvider = LegacyEsiClientProvider
    module.OpenAPIEsiClientProvider = LegacyEsiClientProvider
    sys.modules["esi.clients"] = module
