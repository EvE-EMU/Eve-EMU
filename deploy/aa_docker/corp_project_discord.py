"""Route CorpTools corporation project notifications to Discord by project name.

Reads corptools character notifications (CorporationGoal* / FreelanceProject*) and
posts via **Discord webhook URL** or **aa-discordbot channel ID** (per route).

Example `.env` (match the **goal_name** from CorpTools, case-insensitive substring)::

    AA_CORP_PROJECT_DISCORD_ROUTES=d0 manufacturing:https://discord.com/api/webhooks/…,d1 manufacturing:https://discord.com/api/webhooks/…,d2 manufacturing:https://discord.com/api/webhooks/…

    # e.g. goal names like ``D0 Manufacturing | Maulus`` match ``d0 manufacturing``
    # D1/D2 open projects: **Confirm availability** button → manufacturing sheet; D0 is FCFS.

Channel IDs still work::

    AA_CORP_PROJECT_DISCORD_ROUTES=d0 manufacturing:123456789012345678
    AA_CORP_PROJECT_DISCORD_DEFAULT_CHANNEL_ID=111111111111111111
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
import yaml
from django.core.cache import cache
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

CORP_PROJECT_NOTIFICATION_TYPES: frozenset[str] = frozenset(
    {
        "CorporationGoalCreated",
        "CorporationGoalClosed",
        "CorporationGoalCompleted",
        "CorporationGoalExpired",
        "CorporationGoalLimitReached",
        "FreelanceProjectCreated",
        "FreelanceProjectClosed",
        "FreelanceProjectCompleted",
        "FreelanceProjectExpired",
        "FreelanceProjectLimitReached",
    }
)

CORP_PROJECT_OPEN_TYPES: frozenset[str] = frozenset(
    {
        "CorporationGoalCreated",
        "FreelanceProjectCreated",
    }
)

CORP_PROJECT_CLOSED_TYPES: frozenset[str] = frozenset(
    {
        "CorporationGoalClosed",
        "CorporationGoalCompleted",
        "CorporationGoalExpired",
        "CorporationGoalLimitReached",
        "FreelanceProjectClosed",
        "FreelanceProjectCompleted",
        "FreelanceProjectExpired",
        "FreelanceProjectLimitReached",
    }
)

CORP_PROJECT_COMPLETED_TYPES: frozenset[str] = frozenset(
    {
        "CorporationGoalCompleted",
        "FreelanceProjectCompleted",
    }
)

_DISCORD_EVENT_TITLES: dict[str, str] = {
    "CorporationGoalCreated": "Project created",
    "FreelanceProjectCreated": "Project created",
    "CorporationGoalCompleted": "Project completed",
    "FreelanceProjectCompleted": "Project completed",
    "CorporationGoalClosed": "Project canceled",
    "FreelanceProjectClosed": "Project canceled",
    "CorporationGoalExpired": "Project expired",
    "FreelanceProjectExpired": "Project expired",
    "CorporationGoalLimitReached": "Project limit reached",
    "FreelanceProjectLimitReached": "Project limit reached",
}

CORP_PROJECT_DISCORD_SCOPE = "esi-corporations.read_projects.v1"
_CORP_PROJECT_ESI_SCOPES = [CORP_PROJECT_DISCORD_SCOPE]


def ensure_corp_project_esi_scope_in_db() -> None:
    """Charlink only offers scopes present in django-esi ``Scope`` (sync from CCP list)."""
    try:
        from esi.models import Scope
    except ImportError:
        return
    Scope.objects.get_or_create(
        name=CORP_PROJECT_DISCORD_SCOPE,
        defaults={
            "help_text": "Read corporation projects (corp project Discord alerts)",
        },
    )
_ESI_PROJECT_CACHE_SECONDS = 180
_ITEM_IMAGE_SIZE = 64

_EVENT_COLOURS: dict[str, int] = {
    "opened": 5763719,
    "completed": 3066993,
    "closed": 9807270,
    "expired": 9807270,
    "limit": 15158332,
}

_DEFAULT_CLAIM_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/12nqEHK_g4vAqRmAMJxr8GRaXRaoYcqtOL7So0zdNMhI/edit"
)


@dataclass(frozen=True)
class CorpProjectDestination:
    channel_id: int | None = None
    webhook_url: str | None = None

    @property
    def label(self) -> str:
        if self.webhook_url:
            return "webhook"
        if self.channel_id is not None:
            return f"channel {self.channel_id}"
        return "unknown"


@dataclass(frozen=True)
class CorpProjectRoute:
    pattern: str
    destination: CorpProjectDestination


def _is_discord_webhook_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    return host.endswith("discord.com") and "/api/webhooks/" in path


def _parse_destination(raw: str) -> CorpProjectDestination | None:
    raw = raw.strip()
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        if not _is_discord_webhook_url(raw):
            logger.warning(
                "corp_project_discord: not a Discord webhook URL (ignored)"
            )
            return None
        return CorpProjectDestination(webhook_url=raw)
    if raw.isdigit():
        return CorpProjectDestination(channel_id=int(raw))
    logger.warning("corp_project_discord: invalid destination %r", raw[:80])
    return None


def corp_project_discord_enabled() -> bool:
    if os.environ.get("AA_CORP_PROJECT_DISCORD_ENABLED", "1").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return False
    return bool(
        parse_corp_project_discord_routes()
        or default_corp_project_discord_destination()
    )


def corp_project_discord_needs_aadiscordbot() -> bool:
    """True when any configured route/default uses a channel ID (not webhooks only)."""
    default = default_corp_project_discord_destination()
    if default and default.channel_id is not None:
        return True
    for route in parse_corp_project_discord_routes():
        if route.destination.channel_id is not None:
            return True
    return False


def parse_corp_project_discord_routes() -> list[CorpProjectRoute]:
    """Parse ``AA_CORP_PROJECT_DISCORD_ROUTES`` (comma-separated ``pattern:dest``).

    ``dest`` is either a numeric Discord channel ID or a full webhook URL.
    Only the **first** ``:`` splits pattern from destination (URLs may contain ``:``).
    """
    raw = os.environ.get("AA_CORP_PROJECT_DISCORD_ROUTES", "").strip()
    if not raw:
        return []

    routes: list[CorpProjectRoute] = []
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        pattern, _, dest_raw = part.partition(":")
        pattern = pattern.strip()
        destination = _parse_destination(dest_raw)
        if not pattern or destination is None:
            logger.warning(
                "corp_project_discord: skipping invalid route entry %r", part
            )
            continue
        routes.append(CorpProjectRoute(pattern=pattern, destination=destination))
    return routes


def default_corp_project_discord_channel() -> int | None:
    raw = os.environ.get("AA_CORP_PROJECT_DISCORD_DEFAULT_CHANNEL_ID", "").strip()
    if not raw.isdigit():
        return None
    return int(raw)


def default_corp_project_discord_webhook() -> str | None:
    raw = os.environ.get("AA_CORP_PROJECT_DISCORD_DEFAULT_WEBHOOK_URL", "").strip()
    if not raw:
        return None
    dest = _parse_destination(raw)
    return dest.webhook_url if dest else None


def default_corp_project_discord_destination() -> CorpProjectDestination | None:
    webhook = default_corp_project_discord_webhook()
    if webhook:
        return CorpProjectDestination(webhook_url=webhook)
    channel_id = default_corp_project_discord_channel()
    if channel_id is not None:
        return CorpProjectDestination(channel_id=channel_id)
    return None


def resolve_corp_project_destination(goal_name: str) -> CorpProjectDestination | None:
    """First matching route wins (order in env)."""
    name_lower = goal_name.lower()
    for route in parse_corp_project_discord_routes():
        if route.pattern.lower() in name_lower:
            return route.destination
    return default_corp_project_discord_destination()


def corp_project_claim_sheet_url() -> str:
    """Google sheet for D1/D2 manufacturing claims (name + quantity)."""
    return (
        os.environ.get("AA_CORP_PROJECT_CLAIM_SHEET_URL", _DEFAULT_CLAIM_SHEET_URL).strip()
        or _DEFAULT_CLAIM_SHEET_URL
    )


def manufacturing_tier(goal_name: str) -> str | None:
    """``d0``, ``d1``, or ``d2`` when goal_name matches divisional manufacturing."""
    name = goal_name.lower()
    if "d2 manufacturing" in name:
        return "d2"
    if "d1 manufacturing" in name:
        return "d1"
    if "d0 manufacturing" in name:
        return "d0"
    return None


def completed_discord_tiers() -> frozenset[str]:
    """Manufacturing tiers that post to Discord on **Completed** (default: D0 only)."""
    raw = os.environ.get("AA_CORP_PROJECT_DISCORD_COMPLETED_TIERS", "d0").strip()
    if not raw:
        return frozenset()
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def goal_name_posts_completed_discord(goal_name: str) -> bool:
    tier = manufacturing_tier(goal_name)
    if tier is None or tier not in completed_discord_tiers():
        return False
    return resolve_corp_project_destination(goal_name) is not None


_AVAILABILITY_BUTTON_LABEL = "Confirm availability"


def goal_name_needs_claim_button(goal_name: str) -> bool:
    """D1/D2 use the manufacturing sheet; D0 is first-come-first-served in corp projects."""
    return manufacturing_tier(goal_name) in ("d1", "d2")


def should_show_availability_button(notification) -> bool:
    """Link button for open D1/D2 jobs (created alert + daily digest), not completed/closed."""
    if notification.notification_type in CORP_PROJECT_CLOSED_TYPES:
        return False
    notif_text = (
        notification.notification_text.notification_text
        if notification.notification_text
        else None
    )
    goal_name = parse_goal_name(notif_text) or ""
    return goal_name_needs_claim_button(goal_name)


def build_availability_button_components(
    goal_name: str,
    *,
    label: str = _AVAILABILITY_BUTTON_LABEL,
) -> list[dict[str, Any]] | None:
    """Discord link button (webhooks) for D1/D2 manufacturing sheet."""
    if not goal_name_needs_claim_button(goal_name):
        return None
    url = corp_project_claim_sheet_url()[:512]
    if not url.startswith("http"):
        return None
    return [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 5,
                    "label": label[:80],
                    "url": url,
                }
            ],
        }
    ]


def build_claim_button_components(goal_name: str) -> list[dict[str, Any]] | None:
    """Alias for ``build_availability_button_components``."""
    return build_availability_button_components(goal_name)


def _append_availability_link_field(embed: dict[str, Any], url: str) -> None:
    """Fallback when posting via aa-discordbot channel ID (no raw components API)."""
    fields = list(embed.get("fields") or [])
    fields.append(
        {
            "name": _AVAILABILITY_BUTTON_LABEL,
            "value": f"[Open manufacturing sheet]({url[:512]})",
            "inline": False,
        }
    )
    embed["fields"] = fields


def _cache_key(notification_id: int) -> str:
    return f"corp_project_discord:v1:{notification_id}"


def _goal_dedupe_cache_key(goal_id: str, event_kind: str) -> str:
    return f"corp_project_discord:goal:v1:{goal_id}:{event_kind}"


def _daily_digest_cache_key(goal_id: str, digest_date: str) -> str:
    return f"corp_project_discord:daily:v1:{goal_id}:{digest_date}"


def _daily_digest_timezone() -> ZoneInfo:
    tz_name = os.environ.get(
        "AA_CORP_PROJECT_DISCORD_DAILY_TZ", "America/New_York"
    ).strip() or "America/New_York"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        logger.warning(
            "corp_project_discord: invalid AA_CORP_PROJECT_DISCORD_DAILY_TZ=%r, "
            "using America/New_York",
            tz_name,
        )
        return ZoneInfo("America/New_York")


def _today_digest_date() -> str:
    return timezone.now().astimezone(_daily_digest_timezone()).date().isoformat()


def _already_sent_daily_digest(goal_id: str, digest_date: str) -> bool:
    return bool(cache.get(_daily_digest_cache_key(goal_id, digest_date)))


def _mark_sent_daily_digest(goal_id: str, digest_date: str) -> None:
    cache.set(_daily_digest_cache_key(goal_id, digest_date), "1", timeout=60 * 60 * 48)


def _dedupe_by_goal_enabled() -> bool:
    return os.environ.get("AA_CORP_PROJECT_DISCORD_DEDUPE_BY_GOAL", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _already_sent(notification_id: int) -> bool:
    return bool(cache.get(_cache_key(notification_id)))


def _mark_sent(notification_id: int) -> None:
    cache.set(_cache_key(notification_id), "1", timeout=60 * 60 * 24 * 30)


def _already_sent_goal(goal_id: str, event_kind: str) -> bool:
    return bool(cache.get(_goal_dedupe_cache_key(goal_id, event_kind)))


def _mark_sent_goal(goal_id: str, event_kind: str) -> None:
    cache.set(_goal_dedupe_cache_key(goal_id, event_kind), "1", timeout=60 * 60 * 24 * 30)


def parse_notification_payload(notification_text: str | None) -> dict[str, Any]:
    if not notification_text:
        return {}
    try:
        data = yaml.safe_load(notification_text)
    except yaml.YAMLError:
        logger.debug("corp_project_discord: yaml parse failed", exc_info=True)
        return {}
    return data if isinstance(data, dict) else {}


def parse_goal_name(notification_text: str | None) -> str | None:
    data = parse_notification_payload(notification_text)
    goal = data.get("goal_name")
    if goal is None:
        return None
    return str(strip_tags(str(goal))).strip() or None


def parse_goal_id(notification_text: str | None) -> str | None:
    data = parse_notification_payload(notification_text)
    goal_id = data.get("goal_id")
    if goal_id is None:
        return None
    return str(goal_id)


def _event_kind(notification_type: str) -> str:
    lowered = notification_type.lower()
    if "created" in lowered:
        return "opened"
    if "completed" in lowered:
        return "completed"
    if "closed" in lowered:
        return "closed"
    if "expired" in lowered:
        return "expired"
    if "limit" in lowered:
        return "limit"
    return "opened"


def _discord_event_title(notification_type: str) -> str:
    return _DISCORD_EVENT_TITLES.get(notification_type, "Project updated")


def _format_isk(amount: Any) -> str:
    if amount is None:
        return "—"
    try:
        return f"{float(amount):,.2f} ISK"
    except (TypeError, ValueError):
        return "—"


def _format_qty(amount: Any) -> str:
    if amount is None:
        return "—"
    try:
        return f"{int(amount):,}"
    except (TypeError, ValueError):
        return "—"


def _item_name_from_goal_name(goal_name: str) -> str | None:
    if "|" not in goal_name:
        return None
    item = goal_name.split("|", 1)[1].strip()
    return item or None


def _resolve_character_name(character_id: int | None) -> str:
    if not character_id:
        return "Unknown"
    from corptools.models import EveName

    char, _ = EveName.objects.get_or_create_from_esi(int(character_id))
    return char.name


def _resolve_type_id_from_sde(item_name: str) -> int | None:
    try:
        from eve_sde.models import ItemType
    except ImportError:
        return None
    name = item_name.strip()
    if not name:
        return None
    row = ItemType.objects.filter(name__iexact=name).first()
    if row is None:
        row = ItemType.objects.filter(name__icontains=name).order_by("id").first()
    return int(row.id) if row else None


def _resolve_type_id_from_group(group_id: int) -> int | None:
    try:
        from eve_sde.models import ItemType
    except ImportError:
        return None
    row = (
        ItemType.objects.filter(group_id=int(group_id))
        .order_by("id")
        .only("id")
        .first()
    )
    return int(row.id) if row else None


def _group_id_from_project_detail(detail: dict[str, Any]) -> int | None:
    configuration = detail.get("configuration")
    blocks: list[dict[str, Any]] = []
    inner = _unwrap_esi_configuration(configuration)
    if inner:
        blocks.append(inner)
    elif isinstance(configuration, dict):
        for value in configuration.values():
            if isinstance(value, dict):
                blocks.append(value)

    for block in blocks:
        for entry in block.get("items") or []:
            if not isinstance(entry, dict):
                continue
            if "group_id" in entry:
                return int(entry["group_id"])
            for nested in entry.values():
                if isinstance(nested, dict) and "group_id" in nested:
                    return int(nested["group_id"])
    return None


def resolve_project_type_id(
    detail: dict[str, Any] | None, goal_name: str
) -> tuple[int | None, str | None]:
    """Return (type_id, item_name) from ESI project detail and/or SDE."""
    item_name = _item_name_from_goal_name(goal_name)
    type_id = _type_id_from_project_detail(detail) if detail else None
    if type_id is None and detail:
        group_id = _group_id_from_project_detail(detail)
        if group_id is not None:
            type_id = _resolve_type_id_from_group(group_id)
    if type_id is None and item_name:
        type_id = _resolve_type_id_from_sde(item_name)
    return type_id, item_name


def _type_image_url(type_id: int, item_name: str | None = None) -> str:
    """Item art for Discord (64×64). Capital/components often have no 3D render — use icon."""
    from allianceauth.eveonline.evelinks import eveimageserver

    size = _ITEM_IMAGE_SIZE
    name = (item_name or "").strip().lower()
    use_icon = name.startswith("capital") or name.startswith("standup ")
    if use_icon:
        return eveimageserver.type_icon_url(int(type_id), size=size)
    return eveimageserver.type_render_url(int(type_id), size=size)


def _unwrap_esi_configuration(configuration: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(configuration, dict):
        return {}
    for value in configuration.values():
        if isinstance(value, dict):
            return value
    return {}


def _type_id_from_project_detail(detail: dict[str, Any]) -> int | None:
    configuration = detail.get("configuration")
    blocks: list[dict[str, Any]] = []
    inner = _unwrap_esi_configuration(configuration)
    if inner:
        blocks.append(inner)
    elif isinstance(configuration, dict):
        for value in configuration.values():
            if isinstance(value, dict):
                blocks.append(value)

    for block in blocks:
        for entry in block.get("items") or []:
            if not isinstance(entry, dict):
                continue
            if "type_id" in entry:
                return int(entry["type_id"])
            for nested in entry.values():
                if isinstance(nested, dict) and "type_id" in nested:
                    return int(nested["type_id"])
    return None


def _esi_compatibility_date() -> str:
    """Corp projects require a recent ``X-Compatibility-Date`` (e.g. 2026-05-19)."""
    return os.environ.get("AA_ESI_COMPATIBILITY_DATE", "2026-05-19").strip() or "2026-05-19"


def _model_to_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return None


def _as_mapping(value: Any) -> dict[str, Any]:
    row = _model_to_dict(value)
    return row if row else {}


def _project_names_match(esi_name: str, goal_name: str) -> bool:
    a = strip_tags(str(esi_name or "")).strip()
    b = strip_tags(str(goal_name or "")).strip()
    return bool(a and b and a.lower() == b.lower())


def _projects_from_listing(listing: Any) -> list[dict[str, Any]]:
    """Normalize django-esi 9 listing (dict or list of page models)."""
    raw: list[Any] = []
    if isinstance(listing, dict):
        raw = list(listing.get("projects") or [])
    elif isinstance(listing, list):
        for page in listing:
            if isinstance(page, dict):
                raw.extend(page.get("projects") or [])
            elif hasattr(page, "projects"):
                raw.extend(page.projects or [])

    projects: list[dict[str, Any]] = []
    for entry in raw:
        row = _model_to_dict(entry)
        if row:
            projects.append(row)
    return projects


def _get_corp_esi_token(corp_id: int):
    """Character token with ``esi-corporations.read_projects.v1`` for this corp."""
    from allianceauth.eveonline.models import EveCharacter
    from corptools.tasks.corporation.utils import get_corp_token
    from esi.models import Token

    explicit = os.environ.get("AA_CORP_PROJECT_DISCORD_ESI_TOKEN_ID", "").strip()
    if explicit.isdigit():
        token = Token.objects.filter(pk=int(explicit)).first()
        if token and token.scopes.filter(name=CORP_PROJECT_DISCORD_SCOPE).exists():
            return token
        logger.warning(
            "corp_project_discord: AA_CORP_PROJECT_DISCORD_ESI_TOKEN_ID=%s "
            "missing %s",
            explicit,
            CORP_PROJECT_DISCORD_SCOPE,
        )

    char_ids = EveCharacter.objects.filter(corporation_id=int(corp_id)).values_list(
        "character_id", flat=True
    )
    token = (
        Token.objects.filter(character_id__in=char_ids)
        .filter(scopes__name=CORP_PROJECT_DISCORD_SCOPE)
        .order_by("-pk")
        .first()
    )
    if token is not None:
        return token

    token = get_corp_token(corp_id, _CORP_PROJECT_ESI_SCOPES, False)
    if token is not None:
        return token

    logger.warning(
        "corp_project_discord: no corp token with %s for corporation %s "
        "(re-auth a corp member via Charlink: Corp project Discord)",
        CORP_PROJECT_DISCORD_SCOPE,
        corp_id,
    )
    return None


def _get_esi_projects_tag():
    from esi_clients_compat import openapi_esi_provider_from_app_info_text

    compat = _esi_compatibility_date()
    cache_attr = f"_tag_{compat}"
    if not hasattr(_get_esi_projects_tag, cache_attr):
        provider = openapi_esi_provider_from_app_info_text(
            "corp_project_discord",
            tags=["Corporation Projects"],
            compatibility_date=compat,
        )
        setattr(_get_esi_projects_tag, cache_attr, provider.client.Corporation_Projects)
    return getattr(_get_esi_projects_tag, cache_attr)


def invalidate_project_esi_cache(corp_id: int, goal_name: str) -> None:
    cache.delete(f"corp_project_discord:esi:{corp_id}:{goal_name}")


def _fetch_projects_listing_page(
    tag: Any, corp_id: int, token: Any, *, after: str | None = None
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "corporation_id": int(corp_id),
        "token": token,
        "limit": 100,
    }
    if after:
        kwargs["after"] = after
    page = tag.GetCorporationsProjectsListing(**kwargs).result()
    return _as_mapping(page)


def _fetch_all_projects_listing(
    tag: Any, corp_id: int, token: Any
) -> list[dict[str, Any]]:
    """Cursor-paginated ``GET /corporations/{id}/projects`` (use ``result()``, not ``results()``)."""
    all_projects: list[dict[str, Any]] = []
    after: str | None = "0"
    seen_after: set[str] = set()

    while after is not None:
        if after in seen_after:
            break
        seen_after.add(after)
        page = _fetch_projects_listing_page(tag, corp_id, token, after=after)
        batch = _projects_from_listing(page)
        all_projects.extend(batch)
        cursor = _as_mapping(page.get("cursor"))
        next_after = cursor.get("after")
        if not next_after or str(next_after) == after:
            break
        after = str(next_after)

    return all_projects


def _merge_listing_and_detail(
    listing_row: dict[str, Any], detail: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(listing_row)
    merged.update(detail)
    for key in ("progress", "reward", "contribution"):
        if _as_mapping(detail.get(key)):
            merged[key] = _as_mapping(detail.get(key))
        elif _as_mapping(listing_row.get(key)):
            merged[key] = _as_mapping(listing_row.get(key))
    return merged


def fetch_project_detail_from_esi(
    corp_id: int, goal_name: str, *, use_cache: bool = True
) -> dict[str, Any] | None:
    """Load corp project detail from ESI (qty, payout, type_id). Cached briefly."""
    if not corp_id or not goal_name:
        return None

    cache_key = f"corp_project_discord:esi:{corp_id}:{goal_name}"
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached or None

    token = _get_corp_esi_token(int(corp_id))
    if token is None:
        return None

    try:
        tag = _get_esi_projects_tag()
        projects = _fetch_all_projects_listing(tag, int(corp_id), token)
        match = next(
            (p for p in projects if _project_names_match(p.get("name", ""), goal_name)),
            None,
        )
        if not match:
            logger.warning(
                "corp_project_discord: ESI listing has %s projects; no match for %r "
                "(corp %s, token %s, compat %s)",
                len(projects),
                goal_name,
                corp_id,
                token.character_name,
                _esi_compatibility_date(),
            )
            if use_cache:
                cache.set(cache_key, {}, timeout=60)
            return None

        project_id = match.get("id")
        if not project_id:
            return None

        detail_raw = tag.GetCorporationsProjectsDetail(
            corporation_id=int(corp_id),
            project_id=project_id,
            token=token,
        ).result()
        detail_dict = _as_mapping(detail_raw)
        if not detail_dict:
            detail_dict = dict(match)
        else:
            detail_dict = _merge_listing_and_detail(match, detail_dict)

        if use_cache:
            cache.set(cache_key, detail_dict, timeout=_ESI_PROJECT_CACHE_SECONDS)
        return detail_dict
    except Exception:
        logger.warning(
            "corp_project_discord: ESI project lookup failed for %r",
            goal_name,
            exc_info=True,
        )
    if use_cache:
        cache.set(cache_key, {}, timeout=60)
    return None


def _extract_project_stats(detail: dict[str, Any] | None) -> dict[str, Any]:
    """total_qty, total_isk, isk_per_item from ESI corp project detail."""
    empty_stats: dict[str, Any] = {
        "total_qty": None,
        "total_isk": None,
        "isk_per_item": None,
        "progress_current": None,
        "progress_desired": None,
    }
    if not detail:
        return empty_stats

    progress = _as_mapping(detail.get("progress"))
    contribution = _as_mapping(detail.get("contribution"))
    reward = _as_mapping(detail.get("reward"))

    total_qty = progress.get("desired")
    isk_per_item = contribution.get("reward_per_contribution")
    total_isk = reward.get("initial")

    if total_isk is None and total_qty is not None and isk_per_item is not None:
        try:
            total_isk = float(total_qty) * float(isk_per_item)
        except (TypeError, ValueError):
            total_isk = None

    return {
        "total_qty": total_qty,
        "total_isk": total_isk,
        "isk_per_item": isk_per_item,
        "progress_current": progress.get("current"),
        "progress_desired": progress.get("desired"),
    }


def _format_progress(current: Any, desired: Any) -> str | None:
    if current is None or desired is None:
        return None
    try:
        return f"{int(current):,} / {int(desired):,}"
    except (TypeError, ValueError):
        return None


def _project_embed_fields(detail: dict[str, Any] | None) -> list[dict[str, Any]]:
    stats = _extract_project_stats(detail)
    fields: list[dict[str, Any]] = []
    progress = _format_progress(
        stats.get("progress_current"), stats.get("progress_desired")
    )
    if progress:
        fields.append(
            {
                "name": "Progress",
                "value": progress,
                "inline": True,
            }
        )
    fields.extend(
        [
            {
                "name": "Total quantity",
                "value": _format_qty(stats["total_qty"]),
                "inline": True,
            },
            {
                "name": "Total ISK",
                "value": _format_isk(stats["total_isk"]),
                "inline": True,
            },
            {
                "name": "ISK per item",
                "value": _format_isk(stats["isk_per_item"]),
                "inline": True,
            },
        ]
    )
    return fields


def _build_project_description(
    notification_type: str, goal_name: str, actor_name: str
) -> str:
    """Narrative body matching in-game / native Discord corp project webhooks."""
    goal_name = strip_tags(goal_name)
    actor_name = strip_tags(actor_name) or "Unknown"

    if notification_type.endswith("Created"):
        return (
            f"Project {goal_name} has been created by {actor_name} "
            f"and is accepting contributions."
        )
    if notification_type.endswith("Closed"):
        return (
            f"Project {goal_name} has been closed by {actor_name} "
            f"and will not accept further contributions."
        )
    if notification_type.endswith("Completed"):
        return f"Project {goal_name} has been completed."
    if notification_type.endswith("Expired"):
        return (
            f"Project {goal_name} has expired and will not accept further "
            f"contributions."
        )
    if notification_type.endswith("LimitReached"):
        return f"Project {goal_name} has reached its contribution limit."
    return f"Project {goal_name} was updated."


def build_discord_embed(notification, *, digest: bool = False) -> dict[str, Any]:
    """EVE-style Discord embed (corp author, narrative, item render, qty/payout)."""
    from allianceauth.eveonline.evelinks import eveimageserver
    from corptools.models import EveName

    notif_text = (
        notification.notification_text.notification_text
        if notification.notification_text
        else None
    )
    data = parse_notification_payload(notif_text)

    goal_name = parse_goal_name(notif_text) or "Unknown project"
    corp_id = data.get("corporation_id")
    creator_id = data.get("creator_id")
    closer_id = data.get("closer_id")

    corp_name = "Corporation"
    corp_logo_url = None
    if corp_id:
        corp, _ = EveName.objects.get_or_create_from_esi(int(corp_id))
        corp_name = corp.name
        corp_logo_url = eveimageserver.corporation_logo_url(int(corp_id), size=64)

    if notification.notification_type.endswith("Closed") and closer_id:
        actor_name = _resolve_character_name(closer_id)
    else:
        actor_name = _resolve_character_name(creator_id)

    event_kind = _event_kind(notification.notification_type)
    if digest:
        title = "Open project"
        colour = _EVENT_COLOURS.get("opened", 16756480)
        description = (
            f"Project {strip_tags(goal_name)} is still open and accepting contributions."
        )
    else:
        title = _discord_event_title(notification.notification_type)
        colour = _EVENT_COLOURS.get(event_kind, 16756480)
        description = _build_project_description(
            notification.notification_type, goal_name, actor_name
        )

    detail = None
    if corp_id:
        detail = fetch_project_detail_from_esi(
            int(corp_id), goal_name, use_cache=not digest
        )

    if digest and detail:
        stats = _extract_project_stats(detail)
        progress = _format_progress(
            stats.get("progress_current"), stats.get("progress_desired")
        )
        if progress:
            description += f"\n\n**Progress:** {progress} complete."

    type_id, item_name = resolve_project_type_id(detail, goal_name)

    ts = notification.timestamp
    if timezone.is_naive(ts):
        ts = timezone.make_aware(ts, timezone.utc)

    embed: dict[str, Any] = {
        "author": {"name": corp_name},
        "title": title,
        "description": description,
        "color": colour,
        "footer": {"text": "Eve Online"},
        "timestamp": ts.isoformat(),
    }
    if corp_logo_url:
        embed["author"]["icon_url"] = corp_logo_url
    if type_id:
        embed["thumbnail"] = {"url": _type_image_url(int(type_id), item_name)}

    embed["fields"] = _project_embed_fields(detail)

    return embed


def build_discord_message(
    notification,
    *,
    include_availability_button: bool = True,
    digest: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]] | None]:
    """Embed plus **Confirm availability** button for open D1/D2 (same sheet URL)."""
    embed = build_discord_embed(notification, digest=digest)
    notif_text = (
        notification.notification_text.notification_text
        if notification.notification_text
        else None
    )
    goal_name = parse_goal_name(notif_text) or ""
    components = None
    if include_availability_button and should_show_availability_button(notification):
        components = build_availability_button_components(goal_name)
    return embed, components


def send_corp_project_webhook(
    webhook_url: str,
    embed: dict[str, Any],
    components: list[dict[str, Any]] | None = None,
) -> bool:
    payload: dict[str, Any] = {"embeds": [embed]}
    params: dict[str, str] = {"wait": "true"}
    if components:
        payload["components"] = components
        params["with_components"] = "true"
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            params=params,
            timeout=30,
        )
    except requests.RequestException:
        logger.exception("corp_project_discord: webhook request failed")
        return False

    if response.status_code in (200, 204):
        return True
    logger.warning(
        "corp_project_discord: webhook HTTP %s — %s",
        response.status_code,
        (response.text or "")[:300],
    )
    return False


def send_corp_project_discord_message(
    destination: CorpProjectDestination,
    embed: dict[str, Any],
    components: list[dict[str, Any]] | None = None,
) -> bool:
    if destination.webhook_url:
        return send_corp_project_webhook(
            destination.webhook_url, embed, components=components
        )

    if destination.channel_id is None:
        return False

    try:
        from aadiscordbot.tasks import send_channel_message_by_discord_id
    except ImportError:
        logger.warning("corp_project_discord: aadiscordbot not installed")
        return False

    channel_embed = dict(embed)
    if components:
        logger.info(
            "corp_project_discord: channel %s — use a webhook URL in "
            "AA_CORP_PROJECT_DISCORD_ROUTES for a Confirm availability button",
            destination.channel_id,
        )
        _append_availability_link_field(channel_embed, corp_project_claim_sheet_url())
    send_channel_message_by_discord_id.delay(
        destination.channel_id, "", embed=channel_embed
    )
    return True


def _event_lookback_minutes() -> int:
    """How far back to scan Created/Completed notifications (EVE event time).

    Default is at least 3× the poll interval (min 180 minutes) so a missed beat
    cycle or delayed CorpTools notification sync still triggers an alert.
    """
    if os.environ.get("AA_CORP_PROJECT_DISCORD_EVENT_LOOKBACK_MINUTES"):
        return int(os.environ["AA_CORP_PROJECT_DISCORD_EVENT_LOOKBACK_MINUTES"])
    poll_seconds = int(os.environ.get("AA_CORP_PROJECT_DISCORD_POLL_SECONDS", "1800"))
    return max(180, (poll_seconds // 60) * 3)


def collect_outstanding_open_project_notifications(
    days: int | None = None,
) -> dict[str, Any]:
    """Latest Created notification per open ``goal_id`` (not completed/closed)."""
    try:
        from corptools.models import Notification
    except ImportError:
        return {}

    if days is None:
        days = int(os.environ.get("AA_CORP_PROJECT_DISCORD_BACKFILL_DAYS", "365"))

    qs = Notification.objects.filter(
        notification_type__in=CORP_PROJECT_OPEN_TYPES | CORP_PROJECT_CLOSED_TYPES,
    ).select_related("notification_text", "character__character")
    if days > 0:
        since = timezone.now() - timedelta(days=days)
        qs = qs.filter(timestamp__gte=since)

    closed_goal_ids: set[str] = set()
    open_by_goal: dict[str, Any] = {}

    for notification in qs.order_by("timestamp").iterator(chunk_size=500):
        notif_text = (
            notification.notification_text.notification_text
            if notification.notification_text
            else None
        )
        goal_id = parse_goal_id(notif_text)
        if not goal_id:
            continue

        if notification.notification_type in CORP_PROJECT_CLOSED_TYPES:
            closed_goal_ids.add(goal_id)
            continue

        if notification.notification_type not in CORP_PROJECT_OPEN_TYPES:
            continue

        prev = open_by_goal.get(goal_id)
        if prev is None or notification.timestamp >= prev.timestamp:
            open_by_goal[goal_id] = notification

    return {
        gid: open_by_goal[gid]
        for gid in open_by_goal
        if gid not in closed_goal_ids
    }


def _process_corp_project_notifications(
    notification_types: frozenset[str],
    *,
    lookback_minutes: int,
    goal_filter: Any | None = None,
) -> dict[str, int]:
    if not corp_project_discord_enabled():
        return {"skipped": 1, "sent": 0, "examined": 0}

    try:
        from corptools.models import Notification
    except ImportError:
        logger.warning("corp_project_discord: corptools not installed")
        return {"skipped": 1, "sent": 0, "examined": 0}

    since = timezone.now() - timedelta(minutes=max(5, lookback_minutes))
    qs = (
        Notification.objects.filter(
            notification_type__in=notification_types,
            timestamp__gte=since,
        )
        .select_related("notification_text", "character__character")
        .order_by("timestamp")
    )

    sent = 0
    examined = 0
    for notification in qs.iterator(chunk_size=200):
        examined += 1
        if _already_sent(notification.notification_id):
            continue

        goal_name = parse_goal_name(
            notification.notification_text.notification_text
            if notification.notification_text
            else None
        )
        if not goal_name:
            logger.debug(
                "corp_project_discord: no goal_name for notification %s",
                notification.notification_id,
            )
            continue

        if goal_filter is not None and not goal_filter(goal_name):
            continue

        destination = resolve_corp_project_destination(goal_name)
        if destination is None:
            continue

        notif_text = (
            notification.notification_text.notification_text
            if notification.notification_text
            else None
        )
        goal_id = parse_goal_id(notif_text)
        event_kind = _event_kind(notification.notification_type)
        if _dedupe_by_goal_enabled() and goal_id and _already_sent_goal(goal_id, event_kind):
            _mark_sent(notification.notification_id)
            continue

        try:
            embed, components = build_discord_message(notification)
        except Exception:
            logger.exception(
                "corp_project_discord: failed to build message for %r (notification %s)",
                goal_name,
                notification.notification_id,
            )
            continue

        if send_corp_project_discord_message(destination, embed, components):
            _mark_sent(notification.notification_id)
            if _dedupe_by_goal_enabled() and goal_id:
                _mark_sent_goal(goal_id, event_kind)
            sent += 1
            logger.info(
                "corp_project_discord: sent %s for %r -> %s",
                notification.notification_type,
                goal_name,
                destination.label,
            )

    return {"skipped": 0, "sent": sent, "examined": examined}


def process_corp_project_created_alerts() -> dict[str, int]:
    """New/open corp projects (Created notifications), every ~30 minutes."""
    return _process_corp_project_notifications(
        CORP_PROJECT_OPEN_TYPES,
        lookback_minutes=_event_lookback_minutes(),
    )


def process_corp_project_completed_alerts() -> dict[str, int]:
    """Post **Completed** corp projects for configured tiers (default: D0 manufacturing)."""
    if not completed_discord_tiers():
        logger.info("corp_project_discord: completed posting disabled (empty COMPLETED_TIERS)")
        return {"skipped": 1, "sent": 0, "examined": 0}
    return _process_corp_project_notifications(
        CORP_PROJECT_COMPLETED_TYPES,
        lookback_minutes=_event_lookback_minutes(),
        goal_filter=goal_name_posts_completed_discord,
    )


def backfill_completed_corp_project_discord(
    *,
    dry_run: bool = False,
    days: int | None = None,
    force: bool = False,
) -> dict[str, int]:
    """One-shot: post Discord alerts for recent **Completed** notifications (e.g. missed D0)."""
    if not corp_project_discord_enabled() or not completed_discord_tiers():
        return {"skipped": 1, "sent": 0, "examined": 0}

    try:
        from corptools.models import Notification
    except ImportError:
        return {"skipped": 1, "sent": 0, "examined": 0}

    if days is None:
        days = int(os.environ.get("AA_CORP_PROJECT_DISCORD_BACKFILL_DAYS", "365"))
    since = timezone.now() - timedelta(days=max(1, days))

    qs = (
        Notification.objects.filter(
            notification_type__in=CORP_PROJECT_COMPLETED_TYPES,
            timestamp__gte=since,
        )
        .select_related("notification_text", "character__character")
        .order_by("timestamp")
    )

    examined = 0
    latest_by_goal: dict[str, Any] = {}
    for notification in qs.iterator(chunk_size=500):
        examined += 1
        notif_text = (
            notification.notification_text.notification_text
            if notification.notification_text
            else None
        )
        goal_name = parse_goal_name(notif_text)
        if not goal_name or not goal_name_posts_completed_discord(goal_name):
            continue
        goal_id = parse_goal_id(notif_text)
        if not goal_id:
            continue
        prev = latest_by_goal.get(goal_id)
        if prev is None or notification.timestamp >= prev.timestamp:
            latest_by_goal[goal_id] = notification

    sent = 0
    for goal_id, notification in latest_by_goal.items():
        notif_text = (
            notification.notification_text.notification_text
            if notification.notification_text
            else None
        )
        goal_name = parse_goal_name(notif_text) or ""
        if not force and _already_sent(notification.notification_id):
            continue

        destination = resolve_corp_project_destination(goal_name)
        if destination is None:
            continue

        event_kind = _event_kind(notification.notification_type)
        if (
            not force
            and _dedupe_by_goal_enabled()
            and _already_sent_goal(goal_id, event_kind)
        ):
            continue

        if dry_run:
            sent += 1
            continue

        try:
            embed, components = build_discord_message(notification)
        except Exception:
            logger.exception(
                "corp_project_discord backfill completed: build failed for %r",
                goal_name,
            )
            continue

        if send_corp_project_discord_message(destination, embed, components):
            _mark_sent(notification.notification_id)
            if _dedupe_by_goal_enabled():
                _mark_sent_goal(goal_id, event_kind)
            sent += 1

    return {
        "skipped": 0,
        "sent": sent,
        "examined": examined,
        "goals": len(latest_by_goal),
        "dry_run": dry_run,
    }


def process_corp_project_discord_alerts() -> dict[str, int]:
    """Legacy pass kept for compatibility; only created/open alerts are sent."""
    created = process_corp_project_created_alerts()
    return {
        "skipped": created.get("skipped", 0),
        "sent": created.get("sent", 0),
        "examined": created.get("examined", 0),
    }


def post_daily_outstanding_corp_project_digest(
    *,
    force: bool = False,
) -> dict[str, int]:
    """Daily status for still-open routed projects (progress e.g. 3/14) + availability button."""
    if not corp_project_discord_enabled():
        return {"skipped": 1, "sent": 0, "open": 0, "routed": 0}

    open_by_goal = collect_outstanding_open_project_notifications()
    digest_date = _today_digest_date()

    sent = 0
    routed = 0
    for goal_id, notification in open_by_goal.items():
        goal_name = parse_goal_name(
            notification.notification_text.notification_text
            if notification.notification_text
            else None
        )
        if not goal_name:
            continue

        destination = resolve_corp_project_destination(goal_name)
        if destination is None:
            continue

        routed += 1
        if not force and _already_sent_daily_digest(goal_id, digest_date):
            continue

        notif_text = (
            notification.notification_text.notification_text
            if notification.notification_text
            else None
        )
        corp_id = parse_notification_payload(notif_text).get("corporation_id")
        if corp_id:
            invalidate_project_esi_cache(int(corp_id), goal_name)

        try:
            embed, components = build_discord_message(notification, digest=True)
        except Exception:
            logger.exception(
                "corp_project_discord daily: failed to build digest for %r",
                goal_name,
            )
            continue

        if send_corp_project_discord_message(destination, embed, components):
            _mark_sent_daily_digest(goal_id, digest_date)
            sent += 1
            logger.info(
                "corp_project_discord daily: sent %r -> %s",
                goal_name,
                destination.label,
            )

    return {
        "skipped": 0,
        "sent": sent,
        "open": len(open_by_goal),
        "routed": routed,
        "digest_date": digest_date,
    }


def backfill_outstanding_corp_project_discord(
    *,
    dry_run: bool = False,
    days: int | None = None,
    force: bool = False,
) -> dict[str, int]:
    """Post one Discord message per **still-open** corp project (created, not completed/closed).

    Uses the latest ``CorporationGoalCreated`` / ``FreelanceProjectCreated`` notification
    per ``goal_id`` whose name matches ``AA_CORP_PROJECT_DISCORD_ROUTES`` (e.g. d0/d1).
    """
    if not corp_project_discord_enabled():
        return {"skipped": 1, "sent": 0, "open": 0, "routed": 0}

    open_by_goal = collect_outstanding_open_project_notifications(days=days)

    sent = 0
    routed = 0
    for goal_id, notification in open_by_goal.items():

        goal_name = parse_goal_name(
            notification.notification_text.notification_text
            if notification.notification_text
            else None
        )
        if not goal_name:
            continue

        destination = resolve_corp_project_destination(goal_name)
        if destination is None:
            continue

        routed += 1
        event_kind = "opened"
        if (
            not force
            and _dedupe_by_goal_enabled()
            and _already_sent_goal(goal_id, event_kind)
        ):
            continue

        if dry_run:
            logger.info(
                "corp_project_discord backfill [dry-run]: would send %r -> %s",
                goal_name,
                destination.label,
            )
            sent += 1
            continue

        if force:
            notif_text = (
                notification.notification_text.notification_text
                if notification.notification_text
                else None
            )
            corp_id = parse_notification_payload(notif_text).get("corporation_id")
            if corp_id:
                invalidate_project_esi_cache(int(corp_id), goal_name)

        try:
            embed, components = build_discord_message(notification)
        except Exception:
            logger.exception(
                "corp_project_discord backfill: failed to build message for %r",
                goal_name,
            )
            continue

        if send_corp_project_discord_message(destination, embed, components):
            _mark_sent(notification.notification_id)
            if _dedupe_by_goal_enabled():
                _mark_sent_goal(goal_id, event_kind)
            sent += 1
            logger.info(
                "corp_project_discord backfill: sent %r -> %s",
                goal_name,
                destination.label,
            )

    return {
        "skipped": 0,
        "sent": sent,
        "open": len(open_by_goal),
        "routed": routed,
    }
