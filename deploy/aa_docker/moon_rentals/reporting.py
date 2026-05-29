"""Build weekly moon compliance summaries for Discord."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .compliance import refresh_moon_pop_compliance
from .models import MoonPop, MoonPopMinerStatus, default_buyback_program_id


@dataclass
class MinerLine:
    character_name: str
    username: str
    mined_quantity: int
    buyback_status: str
    tracking_number: str
    ore_form: str


@dataclass
class PopReport:
    moon_pop: MoonPop
    miners: list[MinerLine] = field(default_factory=list)
    phase: str = "closed"  # upcoming | active | closed

    @property
    def needs_action(self) -> bool:
        if self.moon_pop.rental_kind != MoonPop.CORP_FALSE_GODS:
            return any(
                m.buyback_status
                in (
                    MoonPopMinerStatus.STATUS_PENDING,
                    MoonPopMinerStatus.STATUS_QUOTED,
                )
                and m.mined_quantity > 0
                for m in self.miners
            )
        return any(
            m.buyback_status != MoonPopMinerStatus.STATUS_CONTRACTED
            and m.mined_quantity > 0
            for m in self.miners
        )


def _ore_form(row: MoonPopMinerStatus) -> str:
    if row.has_compressed and row.has_uncompressed:
        return "both"
    if row.has_compressed:
        return "compressed"
    if row.has_uncompressed:
        return "uncompressed"
    return "—"


def _miner_lines(pop: MoonPop) -> list[MinerLine]:
    rows = []
    for row in pop.miner_statuses.select_related("user").all():
        rows.append(
            MinerLine(
                character_name=row.character_name or row.user.username,
                username=row.user.username,
                mined_quantity=int(row.mined_quantity),
                buyback_status=row.buyback_status,
                tracking_number=row.tracking_number or "",
                ore_form=_ore_form(row),
            )
        )
    return rows


def refresh_pops_for_report(*, lookback_days: int = 21) -> int:
    """Refresh compliance for pops still in or recently past their window."""
    now = timezone.now()
    count = 0
    for pop in MoonPop.objects.all().iterator():
        if pop.compliance_deadline() >= now - timedelta(days=lookback_days):
            refresh_moon_pop_compliance(pop)
            count += 1
    return count


def build_weekly_report(*, refresh: bool = True) -> dict:
    if refresh:
        refresh_pops_for_report()

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    upcoming_end = now + timedelta(days=7)
    site = str(getattr(settings, "SITE_URL", "") or "").rstrip("/")
    buyback_path = f"/buybackprogram/program/"

    action_required: list[PopReport] = []
    in_progress: list[PopReport] = []
    upcoming: list[PopReport] = []
    private_issues: list[PopReport] = []
    ok_closed: list[PopReport] = []

    for pop in MoonPop.objects.select_related("private_owner").all():
        report = PopReport(moon_pop=pop, miners=_miner_lines(pop))
        deadline = pop.compliance_deadline()

        if pop.pop_at > now:
            report.phase = "upcoming"
            if pop.pop_at <= upcoming_end:
                upcoming.append(report)
            continue

        if deadline >= now:
            report.phase = "active"
            if report.needs_action:
                if pop.rental_kind == MoonPop.PRIVATE:
                    private_issues.append(report)
                else:
                    in_progress.append(report)
            continue

        if pop.pop_at < week_ago and deadline < week_ago:
            continue

        report.phase = "closed"
        if report.needs_action:
            if pop.rental_kind == MoonPop.PRIVATE:
                private_issues.append(report)
            else:
                action_required.append(report)
        elif pop.pop_at >= week_ago or deadline >= week_ago:
            ok_closed.append(report)

    return {
        "generated_at": now.isoformat(),
        "site_url": site,
        "week_label": now.strftime("%Y-%m-%d"),
        "action_required": action_required,
        "in_progress": in_progress,
        "upcoming": upcoming,
        "private_issues": private_issues,
        "ok_closed": ok_closed,
        "buyback_program_id": default_buyback_program_id(),
    }
