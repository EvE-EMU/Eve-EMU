"""Build heatmap cells from extraction ledger aggregates."""

from __future__ import annotations

from django.db.models import Sum

from moon_tsar.models import MoonExtractionEvent, MoonHeatmapCell


def refresh_heatmap_for_period(start, end) -> int:
    updated = 0
    events = MoonExtractionEvent.objects.filter(
        popped_at__date__gte=start,
        popped_at__date__lte=end,
    )
    by_label: dict[str, dict] = {}
    for ev in events:
        label = ev.moon_label
        bucket = by_label.setdefault(
            label,
            {
                "system_name": ev.system_name,
                "moon_number": ev.moon_number or 0,
                "m3": 0,
                "count": 0,
            },
        )
        bucket["m3"] += int(ev.total_mined_m3 or 0)
        bucket["count"] += 1

    for label, data in by_label.items():
        expected = max(data["m3"], 1)
        score = min(data["m3"] / expected, 1.0) if expected else 0.0
        MoonHeatmapCell.objects.update_or_create(
            period_start=start,
            period_end=end,
            moon_label=label[:255],
            defaults={
                "system_name": (data["system_name"] or "")[:128],
                "moon_number": data["moon_number"],
                "mined_m3": data["m3"],
                "expected_m3": expected,
                "extraction_count": data["count"],
                "performance_score": score,
            },
        )
        updated += 1
    return updated
