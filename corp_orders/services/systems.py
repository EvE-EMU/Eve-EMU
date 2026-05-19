from __future__ import annotations

from django.db.models import Case, IntegerField, Value, When

from corp_orders.constants import DEFAULT_FINAL_DESTINATION_SYSTEM


def _solar_system_model():
    from eveuniverse.models import EveSolarSystem

    return EveSolarSystem


def default_destination_system_name() -> str:
    """Best default for the form: exact SDE name if possible, else search seed."""
    default = DEFAULT_FINAL_DESTINATION_SYSTEM
    if resolve_solar_system_name(default):
        return default
    for name in search_solar_system_names(default, limit=25):
        if resolve_solar_system_name(name):
            return name
    return default


def resolve_solar_system_name(name: str) -> bool:
    """True if an exact system name exists in the SDE."""
    clean = (name or "").strip()
    if not clean:
        return False
    return _solar_system_model().objects.filter(name__iexact=clean).exists()


def search_solar_system_names(query: str, *, limit: int = 25) -> list[str]:
    """
    Return system names for autocomplete.
    Empty/short query: default system first, then names sharing its prefix (e.g. 3-F*).
  With query: ranked by exact match, prefix, then contains.
    """
    EveSolarSystem = _solar_system_model()
    q = (query or "").strip()
    limit = max(1, min(int(limit), 50))

    if not q:
        return _bootstrap_suggestions(EveSolarSystem, limit)

    ranked = (
        EveSolarSystem.objects.filter(name__icontains=q)
        .annotate(
            rank=Case(
                When(name__iexact=q, then=Value(0)),
                When(name__istartswith=q, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        )
        .order_by("rank", "name")[:limit]
    )
    names = [row.name for row in ranked]
    return _ensure_default_first(names, q)


def _bootstrap_suggestions(EveSolarSystem, limit: int) -> list[str]:
    """Suggestions when the field is focused with no/new query (default + prefix browse)."""
    default = DEFAULT_FINAL_DESTINATION_SYSTEM
    prefix = default.split("-")[0] + "-" if "-" in default else default[:2]
    if len(prefix) < 2:
        prefix = default[:3] if len(default) >= 3 else default

    names: list[str] = []
    if default:
        names.append(default)

    seed = (
        EveSolarSystem.objects.filter(name__istartswith=prefix)
        .order_by("name")
        .values_list("name", flat=True)[: limit + 5]
    )
    for name in seed:
        if name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names[:limit]


def _ensure_default_first(names: list[str], query: str) -> list[str]:
    default = DEFAULT_FINAL_DESTINATION_SYSTEM
    if not default:
        return names
    if default.lower() == query.lower() or default.lower().startswith(query.lower()):
        if default in names:
            names = [default] + [n for n in names if n != default]
        elif query.lower() in default.lower() or default.lower().startswith(query.lower()):
            names = [default, *names]
    return names[:50]
