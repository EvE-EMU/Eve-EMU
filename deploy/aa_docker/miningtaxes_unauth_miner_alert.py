"""@here Discord alert when a non-Auth'ed character mines an alliance moon.

Requested by the user 2026-09-11: "a @here discord message should be sent to
1511747346793238588 if a NONE Auth'ed character mines any of our moons."

"Our moons" = anything that shows up in ``AdminMiningObsLog`` (the
aa-miningtaxes corp mining-observer log -- one row per miner/ore/day/
structure, sourced from aa-moonmining's ESI observer data per the corp's own
policy: "we use aa-moonmining for taxes"). Any of those structures is, by
definition, one of ours.

"Auth'ed" = the mining character has been claimed by a real Alliance Auth
user via SSO (``CharacterOwnership`` exists for it) -- not merely that an
``EveCharacter`` row exists, which ESI/observer sync creates for *any*
character it sees regardless of whether anyone has ever logged into Auth
with it.

Runs periodically via Celery beat (see extensions/celerybeat.py). Dedupes
per character through the Django cache (Redis-backed) so the same
unauthorized miner does not re-ping every run; the cooldown is deliberately
long since a miner without an Auth account is not going to suddenly fix
itself between runs.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_CHANNEL_ID = "1511747346793238588"
DISCORD_API = "https://discord.com/api/v10"
# Re-alert cooldown per unauthorized character, in seconds. 6 hours: frequent
# enough that an ongoing problem keeps surfacing, not so frequent it spams.
REALERT_COOLDOWN_SECONDS = 6 * 60 * 60
LOOKBACK_DAYS = 2


def _channel_id() -> str:
    return os.environ.get(
        "MININGTAXES_UNAUTH_MINER_DISCORD_CHANNEL", DEFAULT_CHANNEL_ID
    ).strip() or DEFAULT_CHANNEL_ID


def _bot_token() -> str:
    return os.environ.get("DISCORD_BOT_TOKEN", "").strip()


def _is_authed_character(character_id: int) -> bool:
    from allianceauth.authentication.models import CharacterOwnership

    return CharacterOwnership.objects.filter(
        character__character_id=character_id
    ).exists()


def _character_name(character_id: int) -> str:
    from allianceauth.eveonline.models import EveCharacter

    ec = EveCharacter.objects.filter(character_id=character_id).first()
    if ec:
        return ec.character_name
    return f"Character #{character_id}"


def _structure_label(observer) -> str:
    name = getattr(observer, "name", None) or getattr(observer, "obs_id", None)
    return str(name) if name else "Unknown structure"


def find_unauthorized_mining_rows(lookback_days: int = LOOKBACK_DAYS):
    """AdminMiningObsLog rows in the lookback window mined by a non-Auth'ed character."""
    import datetime as dt

    from django.utils.timezone import now
    from miningtaxes.models import AdminMiningObsLog

    cutoff = now().date() - dt.timedelta(days=lookback_days)
    rows = (
        AdminMiningObsLog.objects.filter(date__gte=cutoff)
        .select_related("observer", "eve_type")
        .order_by("-date")
    )

    by_miner: dict[int, list] = {}
    for row in rows:
        by_miner.setdefault(row.miner_id, []).append(row)

    unauthorized = {}
    for miner_id, miner_rows in by_miner.items():
        if _is_authed_character(miner_id):
            continue
        unauthorized[miner_id] = miner_rows
    return unauthorized


def _post_discord_here(message: str) -> None:
    import requests

    token = _bot_token()
    if not token:
        logger.warning(
            "miningtaxes_unauth_miner_alert: DISCORD_BOT_TOKEN not set, skipping alert: %s",
            message,
        )
        return

    resp = requests.post(
        f"{DISCORD_API}/channels/{_channel_id()}/messages",
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "EveEmu-UnauthMinerAlert/1.0",
        },
        json={
            "content": message,
            "allowed_mentions": {"parse": ["everyone"]},  # required for @here to actually ping
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        logger.error(
            "miningtaxes_unauth_miner_alert: Discord post failed (%s): %s",
            resp.status_code,
            resp.text[:500],
        )
    else:
        logger.info("miningtaxes_unauth_miner_alert: posted alert for: %s", message[:120])


def check_and_alert_unauthorized_miners(dry_run: bool = False) -> dict:
    from django.core.cache import cache

    unauthorized = find_unauthorized_mining_rows()
    alerted = []
    skipped_cooldown = []

    for miner_id, rows in unauthorized.items():
        cache_key = f"miningtaxes_unauth_alert:{miner_id}"
        if cache.get(cache_key):
            skipped_cooldown.append(miner_id)
            continue

        name = _character_name(miner_id)
        # Most recent row per structure, deduplicated, for a compact summary.
        seen_structures = {}
        for row in rows:
            label = _structure_label(row.observer)
            if label not in seen_structures or row.date > seen_structures[label]:
                seen_structures[label] = row.date
        structure_lines = "\n".join(
            f"  • {label} — last seen {d.isoformat()}"
            for label, d in sorted(seen_structures.items(), key=lambda kv: kv[1], reverse=True)
        )

        message = (
            "@here **Unauthorized miner detected on an alliance moon**\n"
            f"**{name}** (character ID `{miner_id}`) is mining our moons but is "
            "not linked to any Alliance Auth account:\n"
            f"{structure_lines}\n"
            "This character owes moon taxes but Auth cannot bill them without a link."
        )

        if dry_run:
            alerted.append((miner_id, name, message))
            continue

        _post_discord_here(message)
        cache.set(cache_key, True, REALERT_COOLDOWN_SECONDS)
        alerted.append((miner_id, name, message))

    return {
        "alerted": alerted,
        "alerted_count": len(alerted),
        "skipped_cooldown": skipped_cooldown,
    }


def _register_celery_task() -> None:
    try:
        from celery import shared_task
    except Exception:
        return

    @shared_task(name="miningtaxes_unauth_miner_alert.check_unauthorized_miners")
    def check_unauthorized_miners() -> dict:
        result = check_and_alert_unauthorized_miners()
        logger.info(
            "miningtaxes_unauth_miner_alert: periodic check - %d alerted, %d in cooldown",
            result["alerted_count"],
            len(result["skipped_cooldown"]),
        )
        return {
            "alerted_count": result["alerted_count"],
            "skipped_cooldown": result["skipped_cooldown"],
        }

    globals()["check_unauthorized_miners"] = check_unauthorized_miners


def apply_miningtaxes_unauth_miner_alert_patch() -> None:
    if getattr(apply_miningtaxes_unauth_miner_alert_patch, "_applied", False):
        return
    _register_celery_task()
    apply_miningtaxes_unauth_miner_alert_patch._applied = True  # type: ignore[attr-defined]
    logger.info(
        "miningtaxes_unauth_miner_alert: periodic unauthorized-miner Discord "
        "alert registered (channel %s)",
        _channel_id(),
    )
