"""Post moon compliance reports to a Discord webhook."""

from __future__ import annotations

import logging
import os
from typing import Any

import requests
from django.conf import settings

from .models import MoonPop, MoonPopMinerStatus
from .reporting import PopReport

logger = logging.getLogger(__name__)

_STATUS_LABEL = {
    MoonPopMinerStatus.STATUS_CONTRACTED: "Contracted",
    MoonPopMinerStatus.STATUS_QUOTED: "Quoted (no contract)",
    MoonPopMinerStatus.STATUS_PENDING: "Missing buyback",
    MoonPopMinerStatus.STATUS_NONE: "No mining logged",
}


def discord_enabled() -> bool:
    if os.environ.get("MOON_RENTALS_DISCORD_ENABLED", "1").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return False
    return bool(webhook_url())


def webhook_url() -> str:
    return (
        os.environ.get("MOON_RENTALS_DISCORD_WEBHOOK_URL", "").strip()
        or str(getattr(settings, "MOON_RENTALS_DISCORD_WEBHOOK_URL", "") or "").strip()
    )


def _post(payload: dict[str, Any]) -> bool:
    url = webhook_url()
    if not url:
        logger.warning("moon_rentals: MOON_RENTALS_DISCORD_WEBHOOK_URL not set")
        return False
    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        return True
    except Exception:
        logger.exception("moon_rentals: Discord webhook failed")
        return False


def _format_pop_block(report: PopReport, *, include_miners: bool = True) -> str:
    pop = report.moon_pop
    lines = [f"**{pop.location_label}** — pop {pop.pop_at:%Y-%m-%d %H:%M} UTC"]
    if pop.rental_kind == MoonPop.PRIVATE and pop.private_owner:
        lines[0] += f" (private: {pop.private_owner.username})"
    if not include_miners or not report.miners:
        return "\n".join(lines)
    for m in report.miners:
        if m.mined_quantity == 0 and m.buyback_status == MoonPopMinerStatus.STATUS_NONE:
            continue
        label = _STATUS_LABEL.get(m.buyback_status, m.buyback_status)
        extra = ""
        if m.tracking_number:
            extra = f" `{m.tracking_number}`"
        lines.append(
            f"• {m.character_name}: {m.mined_quantity:,} — {label}{extra} ({m.ore_form})"
        )
    return "\n".join(lines)[:1020]


def _embed(
    title: str,
    description: str,
    *,
    color: int = 0x5865F2,
    fields: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    emb: dict[str, Any] = {
        "title": title[:256],
        "description": description[:4090] or "\u200b",
        "color": color,
    }
    if fields:
        emb["fields"] = fields[:25]
    return emb


def build_weekly_discord_payload(report_data: dict) -> dict[str, Any]:
    site = report_data.get("site_url") or ""
    program_id = report_data.get("buyback_program_id", 3)
    buyback_link = f"{site}/buybackprogram/program/{program_id}/calculate/" if site else ""
    schedule_link = f"{site}/miningtaxes/schedule/" if site else ""

    action = report_data.get("action_required") or []
    in_prog = report_data.get("in_progress") or []
    upcoming = report_data.get("upcoming") or []
    private = report_data.get("private_issues") or []
    ok = report_data.get("ok_closed") or []

    summary_lines = [
        f"**Week ending** {report_data.get('week_label', '')}",
        f"**Corp — action required (window closed):** {len(action)}",
        f"**Corp — in progress:** {len(in_prog)}",
        f"**Private — needs buyback:** {len(private)}",
        f"**Completed:** {len(ok)}",
        f"**Upcoming pops (7d):** {len(upcoming)}",
    ]
    if buyback_link:
        summary_lines.append(f"[Moon G00 buyback]({buyback_link})")
    if schedule_link:
        summary_lines.append(f"[Full schedule]({schedule_link})")

    embeds = [
        _embed("Moon ore compliance — weekly", "\n".join(summary_lines), color=0x57F287)
    ]

    if action:
        chunks = []
        for rep in action[:8]:
            chunks.append(_format_pop_block(rep))
        embeds.append(
            _embed(
                "Corp moons — missing contracts",
                "\n\n".join(chunks) or "—",
                color=0xED4245,
            )
        )

    if in_prog:
        chunks = [_format_pop_block(r) for r in in_prog[:8]]
        embeds.append(
            _embed(
                "Corp moons — in progress",
                "\n\n".join(chunks) or "—",
                color=0xFEE75C,
            )
        )

    if private:
        chunks = [_format_pop_block(r) for r in private[:6]]
        embeds.append(
            _embed(
                "Private rentals",
                "\n\n".join(chunks) or "—",
                color=0xEB459E,
            )
        )

    if upcoming:
        lines = [
            f"• {r.moon_pop.location_label} — {r.moon_pop.pop_at:%Y-%m-%d %H:%M} UTC"
            for r in upcoming[:15]
        ]
        embeds.append(
            _embed("Upcoming pops", "\n".join(lines) or "—", color=0x5865F2)
        )

    if ok and len(embeds) < 10:
        lines = [f"• {r.moon_pop.location_label}" for r in ok[:12]]
        embeds.append(
            _embed(
                "Recently completed (all contracted)",
                "\n".join(lines) or "—",
                color=0x57F287,
            )
        )

    return {"embeds": embeds[:10]}


def send_weekly_report(report_data: dict | None = None) -> bool:
    if not discord_enabled():
        return False
    if report_data is None:
        from .reporting import build_weekly_report

        report_data = build_weekly_report(refresh=True)
    payload = build_weekly_discord_payload(report_data)
    return _post(payload)
