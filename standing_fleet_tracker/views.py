from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter

from standing_fleet_tracker import app_settings
from standing_fleet_tracker.models import (
    CharacterMonthlyKPI,
    CharacterScore,
    FleetSession,
    PointLedger,
    ShipFleetStat,
)
from standing_fleet_tracker.services.monthly_kpi import compute_character_monthly_kpi
from standing_fleet_tracker.services.polling import poll_user_characters
from standing_fleet_tracker.services.scoring import user_leaderboard
from standing_fleet_tracker.services.fittings_lookup import fitting_payload
from standing_fleet_tracker.services.ship_fit import fitting_payload_for_character
from standing_fleet_tracker.services.session_report import build_session_report
from standing_fleet_tracker.services.status import (
    get_character_live_status,
    live_fleet_roster,
    live_status_for_user,
)
from standing_fleet_tracker.services.universe import type_name

User = get_user_model()


def _maybe_refresh_user_poll(user) -> None:
    cache_key = f"sft:dashboard_poll:{user.pk}"
    ttl = max(60, min(app_settings.SFT_POLL_INTERVAL_SECONDS, 120))
    if cache.add(cache_key, 1, timeout=ttl):
        poll_user_characters(user)


@login_required
@permission_required("standing_fleet_tracker.basic_access")
def dashboard(request):
    _maybe_refresh_user_poll(request.user)
    my_statuses = live_status_for_user(request.user)
    roster = live_fleet_roster(limit=80)
    chars_needing_scopes = [s for s in my_statuses if s.missing_scopes]
    return render(
        request,
        "standing_fleet_tracker/dashboard.html",
        {
            "my_statuses": my_statuses,
            "roster": roster,
            "poll_interval": app_settings.SFT_POLL_INTERVAL_SECONDS,
            "chars_needing_scopes": chars_needing_scopes,
        },
    )


@login_required
@permission_required("standing_fleet_tracker.basic_access")
def leaderboard(request):
    rows = user_leaderboard(limit=100)
    my_row = next((r for r in rows if r["user"].pk == request.user.pk), None)
    live_by_user: dict[int, str] = {}
    for entry in live_fleet_roster(limit=200):
        owner = CharacterOwnership.objects.filter(character=entry.character).first()
        if not owner:
            continue
        if entry.is_standing_fleet:
            live_by_user[owner.user_id] = entry.standing_label or "Standing"
        elif owner.user_id not in live_by_user:
            live_by_user[owner.user_id] = "In fleet"
    for row in rows:
        row["live_label"] = live_by_user.get(row["user"].pk, "")
    if my_row:
        my_row["live_label"] = live_by_user.get(request.user.pk, "")
    return render(
        request,
        "standing_fleet_tracker/leaderboard.html",
        {"rows": rows, "my_row": my_row, "title": "Standing fleet leaderboard"},
    )


@login_required
@permission_required("standing_fleet_tracker.basic_access")
def lagging_board(request):
    rows = user_leaderboard(limit=200)
    rows.sort(key=lambda r: (r["total_points"], r["penalty_hours"]))
    lagging = [r for r in rows if r["penalty_hours"] > 0 or r["total_points"] < 0][:50]
    return render(
        request,
        "standing_fleet_tracker/lagging_board.html",
        {"rows": lagging, "title": "Needs improvement"},
    )


def _characters_for_user(user):
    return EveCharacter.objects.filter(
        character_ownership__user=user
    ).select_related("standing_fleet_score")


@login_required
@permission_required("standing_fleet_tracker.basic_access")
def user_detail(request, user_id: int):
    user = get_object_or_404(User, pk=user_id)
    characters = list(_characters_for_user(user))
    agg = CharacterScore.objects.filter(character__in=characters).aggregate(
        total=Sum("total_points"),
        standing=Sum("standing_fleet_hours"),
        penalty=Sum("penalty_hours"),
        kills=Sum("kill_bonus_points"),
        pulse=Sum("pulse_points"),
    )
    ledger = PointLedger.objects.filter(user=user).order_by("-created_at")[:50]
    char_statuses = live_status_for_user(user)
    return render(
        request,
        "standing_fleet_tracker/user_detail.html",
        {
            "profile_user": user,
            "characters": characters,
            "char_statuses": char_statuses,
            "agg": agg,
            "ledger": ledger,
        },
    )


@login_required
@permission_required("standing_fleet_tracker.basic_access")
def character_detail(request, character_id: int):
    character = get_object_or_404(EveCharacter, pk=character_id)
    score = CharacterScore.objects.filter(character=character).first()
    sessions = FleetSession.objects.filter(character=character).order_by("-started_at")[:30]
    from standing_fleet_tracker.services.fit_snapshots import find_best_snapshot

    ships_qs = ShipFleetStat.objects.filter(character=character).order_by("-seconds_flown")[:10]
    ships = []
    for s in ships_qs:
        snap = find_best_snapshot(
            character.character_id,
            s.ship_type_id,
            ship_name=s.ship_name or "",
        )
        ships.append(
            {
                "stat": s,
                "ship_type_name": type_name(s.ship_type_id),
                "ship_name": s.ship_name or "",
                "snapshot_id": snap.pk if snap else None,
            }
        )
    ledger = PointLedger.objects.filter(character=character).order_by("-created_at")[:30]
    owner = CharacterOwnership.objects.filter(character=character).select_related("user").first()
    live = get_character_live_status(character)
    if owner and owner.user_id == request.user.pk:
        _maybe_refresh_user_poll(request.user)
        live = get_character_live_status(character)
    return render(
        request,
        "standing_fleet_tracker/character_detail.html",
        {
            "character": character,
            "score": score,
            "sessions": sessions,
            "ships": ships,
            "ledger": ledger,
            "owner": owner,
            "live": live,
        },
    )


@login_required
@permission_required("standing_fleet_tracker.basic_access")
def character_monthly_kpi(request, character_id: int):
    character = get_object_or_404(EveCharacter, pk=character_id)
    now = timezone.now()
    try:
        year = int(request.GET.get("year", now.year))
        month = int(request.GET.get("month", now.month))
    except (TypeError, ValueError):
        year, month = now.year, now.month
    month = max(1, min(12, month))

    kpi = CharacterMonthlyKPI.objects.filter(
        character=character, year=year, month=month
    ).first()
    if request.GET.get("refresh"):
        kpi = compute_character_monthly_kpi(character, year, month)

    kpis = list(
        CharacterMonthlyKPI.objects.filter(character=character).order_by("-year", "-month")[:24]
    )
    return render(
        request,
        "standing_fleet_tracker/character_monthly_kpi.html",
        {
            "character": character,
            "year": year,
            "month": month,
            "kpi": kpi,
            "kpis": kpis,
        },
    )


@login_required
@permission_required("standing_fleet_tracker.basic_access")
def session_detail(request, session_id: int):
    session = get_object_or_404(
        FleetSession.objects.select_related("character"),
        pk=session_id,
    )
    report = build_session_report(session)
    return render(
        request,
        "standing_fleet_tracker/session_detail.html",
        {
            "character": session.character,
            "report": report,
        },
    )


@login_required
@permission_required("standing_fleet_tracker.basic_access")
@require_GET
def ship_fit_json(request, ship_type_id: int):
    raw_character_id = request.GET.get("character_id")
    if raw_character_id:
        try:
            character_id = int(raw_character_id)
        except (TypeError, ValueError):
            return JsonResponse({"error": "Invalid character_id"}, status=400)
        snapshot_id = None
        raw_snapshot = request.GET.get("snapshot_id")
        if raw_snapshot:
            try:
                snapshot_id = int(raw_snapshot)
            except (TypeError, ValueError):
                return JsonResponse({"error": "Invalid snapshot_id"}, status=400)
        use_live = request.GET.get("live", "").lower() in ("1", "true", "yes")
        session_id = None
        raw_session = request.GET.get("session_id")
        if raw_session:
            try:
                session_id = int(raw_session)
            except (TypeError, ValueError):
                return JsonResponse({"error": "Invalid session_id"}, status=400)
        ship_name = (request.GET.get("ship_name") or "").strip()
        first_seen = parse_datetime(request.GET.get("first_seen") or "")
        last_seen = parse_datetime(request.GET.get("last_seen") or "")
        return JsonResponse(
            fitting_payload_for_character(
                character_id,
                ship_type_id,
                request=request,
                snapshot_id=snapshot_id,
                session_id=session_id,
                ship_name=ship_name,
                first_seen=first_seen,
                last_seen=last_seen,
                use_live=use_live,
            )
        )
    return JsonResponse(fitting_payload(ship_type_id))
