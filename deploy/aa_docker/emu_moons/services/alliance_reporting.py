"""Alliance-wide KPIs and leaderboards for EMU Moons."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from emu_moons.access import tax_effective_date
from emu_moons.models import EmuInvoice

OPEN_STATUSES = (
    EmuInvoice.STATUS_OPEN,
    EmuInvoice.STATUS_PARTIAL,
    EmuInvoice.STATUS_CORP_LIABLE,
)

DUE_EXPR = (
    Coalesce(F("original_tax_isk"), Value(0), output_field=DecimalField())
    + Coalesce(F("penalty_isk"), Value(0), output_field=DecimalField())
    - Coalesce(F("amount_paid_isk"), Value(0), output_field=DecimalField())
)


@dataclass(frozen=True)
class PeriodKpis:
    tax_generated: Decimal
    tax_collected: Decimal
    volume_m3: Decimal
    invoice_count: int
    outstanding: Decimal
    open_count: int


@dataclass(frozen=True)
class LeaderboardRow:
    label: str
    sublabel: str
    value: Decimal
    link_username: str | None = None
    corp_id: int | None = None


def _active_qs():
    cutoff = tax_effective_date()
    return EmuInvoice.objects.exclude(status=EmuInvoice.STATUS_VOID).filter(
        due_at__gte=cutoff,
        issued_at__date__gte=cutoff,
    )


def _period_starts():
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return month_start, year_start


def _kpis_for_period(qs, *, start=None, end=None) -> PeriodKpis:
    if start is not None:
        qs = qs.filter(issued_at__gte=start)
    if end is not None:
        qs = qs.filter(issued_at__lt=end)

    agg = qs.aggregate(
        tax_generated=Coalesce(Sum("original_tax_isk"), Value(0), output_field=DecimalField()),
        volume_m3=Coalesce(Sum("total_volume_m3"), Value(0), output_field=DecimalField()),
        invoice_count=Count("pk"),
    )

    paid_qs = qs.filter(amount_paid_isk__gt=0, paid_at__isnull=False)
    if start is not None:
        paid_qs = paid_qs.filter(paid_at__gte=start)
    if end is not None:
        paid_qs = paid_qs.filter(paid_at__lt=end)

    collected = paid_qs.aggregate(
        total=Coalesce(Sum("amount_paid_isk"), Value(0), output_field=DecimalField()),
    )["total"]

    open_qs = qs.filter(status__in=OPEN_STATUSES)
    outstanding = open_qs.aggregate(
        total=Coalesce(Sum(DUE_EXPR), Value(0), output_field=DecimalField()),
    )["total"]

    return PeriodKpis(
        tax_generated=Decimal(str(agg["tax_generated"] or 0)),
        tax_collected=Decimal(str(collected or 0)),
        volume_m3=Decimal(str(agg["volume_m3"] or 0)),
        invoice_count=int(agg["invoice_count"] or 0),
        outstanding=max(Decimal(str(outstanding or 0)), Decimal("0")),
        open_count=open_qs.count(),
    )


def _corp_leaderboard(qs, metric: str, *, limit: int = 10) -> list[LeaderboardRow]:
    base = qs.filter(corporation_id__isnull=False).exclude(corporation_name="")
    if metric == "volume":
        rows = (
            base.values("corporation_id", "corporation_name")
            .annotate(value=Coalesce(Sum("total_volume_m3"), Value(0), output_field=DecimalField()))
            .order_by("-value")[:limit]
        )
    elif metric == "tax_paid":
        rows = (
            base.values("corporation_id", "corporation_name")
            .annotate(value=Coalesce(Sum("amount_paid_isk"), Value(0), output_field=DecimalField()))
            .order_by("-value")[:limit]
        )
    elif metric == "outstanding":
        rows = (
            base.filter(status__in=OPEN_STATUSES)
            .values("corporation_id", "corporation_name")
            .annotate(value=Coalesce(Sum(DUE_EXPR), Value(0), output_field=DecimalField()))
            .order_by("-value")[:limit]
        )
    else:
        return []

    return [
        LeaderboardRow(
            label=r["corporation_name"] or f"Corp {r['corporation_id']}",
            sublabel=f"ID {r['corporation_id']}",
            value=Decimal(str(r["value"] or 0)),
            corp_id=int(r["corporation_id"]),
        )
        for r in rows
        if Decimal(str(r["value"] or 0)) > 0
    ]


def _individual_leaderboard(qs, metric: str, *, limit: int = 10) -> list[LeaderboardRow]:
    base = qs.select_related("user")
    if metric == "volume":
        rows = (
            base.values("user_id", "user__username")
            .annotate(value=Coalesce(Sum("total_volume_m3"), Value(0), output_field=DecimalField()))
            .order_by("-value")[:limit]
        )
    elif metric == "tax_paid":
        rows = (
            base.values("user_id", "user__username")
            .annotate(value=Coalesce(Sum("amount_paid_isk"), Value(0), output_field=DecimalField()))
            .order_by("-value")[:limit]
        )
    elif metric == "outstanding":
        rows = (
            base.filter(status__in=OPEN_STATUSES)
            .values("user_id", "user__username")
            .annotate(value=Coalesce(Sum(DUE_EXPR), Value(0), output_field=DecimalField()))
            .order_by("-value")[:limit]
        )
    else:
        return []

    result: list[LeaderboardRow] = []
    for r in rows:
        val = Decimal(str(r["value"] or 0))
        if val <= 0:
            continue
        username = r["user__username"] or f"user-{r['user_id']}"
        char_hint = ""
        if metric == "volume":
            top_char = (
                qs.filter(user_id=r["user_id"])
                .order_by("-total_volume_m3")
                .values_list("character_name", flat=True)
                .first()
            )
            if top_char:
                char_hint = top_char
        result.append(
            LeaderboardRow(
                label=username,
                sublabel=char_hint or "Alliance Auth account",
                value=val,
                link_username=username,
            )
        )
    return result


def _kpi_to_dict(kpi: PeriodKpis) -> dict:
    return {
        "tax_generated": kpi.tax_generated,
        "tax_collected": kpi.tax_collected,
        "volume_m3": kpi.volume_m3,
        "invoice_count": kpi.invoice_count,
        "outstanding": kpi.outstanding,
        "open_count": kpi.open_count,
    }


def _rows_to_dicts(rows: list[LeaderboardRow]) -> list[dict]:
    return [
        {
            "label": r.label,
            "sublabel": r.sublabel,
            "value": r.value,
            "link_username": r.link_username,
            "corp_id": r.corp_id,
        }
        for r in rows
    ]


def build_alliance_dashboard_context(*, leaderboard_limit: int = 10) -> dict:
    qs = _active_qs()
    month_start, year_start = _period_starts()
    now = timezone.now()

    all_time = _kpis_for_period(qs)
    month = _kpis_for_period(qs, start=month_start)
    year = _kpis_for_period(qs, start=year_start)

    leaderboards = {
        "corp_volume": _corp_leaderboard(qs, "volume", limit=leaderboard_limit),
        "corp_tax_paid": _corp_leaderboard(qs, "tax_paid", limit=leaderboard_limit),
        "corp_outstanding": _corp_leaderboard(qs, "outstanding", limit=leaderboard_limit),
        "user_volume": _individual_leaderboard(qs, "volume", limit=leaderboard_limit),
        "user_tax_paid": _individual_leaderboard(qs, "tax_paid", limit=leaderboard_limit),
        "user_outstanding": _individual_leaderboard(
            qs, "outstanding", limit=leaderboard_limit
        ),
    }

    return {
        "kpi_all_time": _kpi_to_dict(all_time),
        "kpi_month": _kpi_to_dict(month),
        "kpi_year": _kpi_to_dict(year),
        "period_month_label": month_start.strftime("%B %Y"),
        "period_year_label": str(year_start.year),
        "leaderboards": {key: _rows_to_dicts(val) for key, val in leaderboards.items()},
        "generated_at": now,
        # Legacy keys for any cached/old template fragments
        "total_tax": all_time.tax_generated,
        "total_paid": all_time.tax_collected,
        "total_penalty": Decimal("0"),
        "outstanding": all_time.outstanding,
        "open_count": all_time.open_count,
    }
