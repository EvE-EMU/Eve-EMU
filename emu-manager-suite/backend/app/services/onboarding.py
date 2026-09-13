"""Onboarding checklist, achievements, and admission KPI ranking."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.onboarding import (
    AdmissionConfig,
    AdmissionKpi,
    OnboardingProgress,
    OnboardingTask,
)
from app.models.tools import AuditProfile, LinkedCharacter, SsoUser
from app.models.character_skills import CharacterSkillLevel
from app.models.onboarding import CharacterStanding
from app.services.audit_scopes import parse_granted_scopes
from app.services.zkill import fetch_character_stats

DEFAULT_TASKS: list[dict[str, Any]] = [
    {
        "slug": "sso_login",
        "title": "Log in with EVE SSO",
        "description": "Authenticate so EMUMS can sync your characters.",
        "category": "setup",
        "points": 10,
        "sort_order": 10,
        "window_id": "",
        "auto_check": "sso_login",
    },
    {
        "slug": "audit_sync",
        "title": "Run character audit sync",
        "description": "Open Character Audit and sync assets, skills, and wallet.",
        "category": "setup",
        "points": 20,
        "sort_order": 20,
        "window_id": "char-audit",
        "auto_check": "audit_sync",
    },
    {
        "slug": "visit_storefront",
        "title": "Browse the storefront",
        "description": "Open Industry → Storefront and review corp stock.",
        "category": "tools",
        "points": 10,
        "sort_order": 30,
        "window_id": "ip-storefront",
        "auto_check": "",
    },
    {
        "slug": "try_build_planner",
        "title": "Try the build planner",
        "description": "Open Build Planner and calculate a production plan.",
        "category": "tools",
        "points": 15,
        "sort_order": 40,
        "window_id": "ip-planner",
        "auto_check": "",
    },
    {
        "slug": "try_intel_paste",
        "title": "Try Intel Paste",
        "description": "Paste a local list in Utilities → Intel Paste.",
        "category": "tools",
        "points": 10,
        "sort_order": 50,
        "window_id": "suite-intel",
        "auto_check": "",
    },
    {
        "slug": "link_alt",
        "title": "Link an alt character",
        "description": "Add at least one alt via SSO for full roster coverage.",
        "category": "setup",
        "points": 15,
        "sort_order": 25,
        "window_id": "char-audit",
        "auto_check": "link_alt",
    },
    {
        "slug": "read_about",
        "title": "Read About EMUMS",
        "description": "Open Utilities → About and review available tools.",
        "category": "social",
        "points": 5,
        "sort_order": 5,
        "window_id": "about",
        "auto_check": "",
    },
]

DEFAULT_KPIS: list[dict[str, Any]] = [
    {
        "slug": "skillpoints",
        "label": "Skill points",
        "description": "Total trained SP (target 20M+)",
        "weight": 1.5,
        "metric_key": "sp",
        "min_value": 0,
        "target_value": 20_000_000,
        "sort_order": 10,
    },
    {
        "slug": "killboard",
        "label": "Killboard activity",
        "description": "Ships destroyed on zKill",
        "weight": 1.0,
        "metric_key": "kills",
        "min_value": 0,
        "target_value": 50,
        "sort_order": 20,
    },
    {
        "slug": "kd_ratio",
        "label": "K/D ratio",
        "description": "Kills / max(losses, 1)",
        "weight": 1.0,
        "metric_key": "kd",
        "min_value": 0,
        "target_value": 1.5,
        "sort_order": 30,
    },
    {
        "slug": "scopes",
        "label": "ESI scopes",
        "description": "Fraction of useful scopes granted",
        "weight": 1.2,
        "metric_key": "scopes",
        "min_value": 0,
        "target_value": 1.0,
        "sort_order": 40,
    },
    {
        "slug": "onboarding",
        "label": "Onboarding progress",
        "description": "Share of onboarding tasks completed",
        "weight": 1.5,
        "metric_key": "onboarding",
        "min_value": 0,
        "target_value": 1.0,
        "sort_order": 50,
    },
    {
        "slug": "assets",
        "label": "Asset footprint",
        "description": "Estimated assets value (ISK)",
        "weight": 0.8,
        "metric_key": "assets",
        "min_value": 0,
        "target_value": 500_000_000,
        "sort_order": 60,
    },
    {
        "slug": "standings",
        "label": "Standings average",
        "description": "Average ESI contact standing (sync via Standings Sync tool)",
        "weight": 0.7,
        "metric_key": "standings",
        "min_value": -5,
        "target_value": 5,
        "sort_order": 70,
    },
]


async def ensure_onboarding_defaults(session: AsyncSession) -> None:
    for task in DEFAULT_TASKS:
        existing = await session.scalar(select(OnboardingTask).where(OnboardingTask.slug == task["slug"]))
        if existing:
            continue
        session.add(OnboardingTask(**task))
    for kpi in DEFAULT_KPIS:
        existing = await session.scalar(select(AdmissionKpi).where(AdmissionKpi.slug == kpi["slug"]))
        if existing:
            continue
        session.add(AdmissionKpi(**kpi, active=True))
    cfg = await session.scalar(select(AdmissionConfig).limit(1))
    if not cfg:
        session.add(AdmissionConfig(admit_threshold=60.0, review_threshold=40.0))
    await session.flush()


async def _auto_complete_flags(session: AsyncSession, character_id: int) -> dict[str, bool]:
    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    profile = await session.scalar(select(AuditProfile).where(AuditProfile.character_id == character_id))
    alts = (
        await session.scalars(select(LinkedCharacter).where(LinkedCharacter.owner_user_id == (user.id if user else -1)))
    ).all() if user else []
    return {
        "sso_login": user is not None,
        "audit_sync": bool(profile and profile.last_sync_at),
        "link_alt": len(alts) > 0,
    }


async def onboarding_status(session: AsyncSession, *, character_id: int, character_name: str = "") -> dict[str, Any]:
    await ensure_onboarding_defaults(session)
    tasks = (
        await session.scalars(
            select(OnboardingTask).where(OnboardingTask.active.is_(True)).order_by(OnboardingTask.sort_order)
        )
    ).all()
    progress_rows = (
        await session.scalars(select(OnboardingProgress).where(OnboardingProgress.character_id == character_id))
    ).all()
    by_task = {int(p.task_id): p for p in progress_rows}
    flags = await _auto_complete_flags(session, character_id)

    items: list[dict[str, Any]] = []
    earned = 0
    total_points = 0
    completed = 0
    for task in tasks:
        total_points += int(task.points)
        prog = by_task.get(int(task.id))
        done = bool(prog and prog.completed)
        if not done and task.auto_check and flags.get(task.auto_check):
            done = True
            if not prog:
                prog = OnboardingProgress(
                    character_id=character_id,
                    character_name=character_name,
                    task_id=int(task.id),
                    completed=True,
                    completed_at=datetime.now(UTC),
                )
                session.add(prog)
            else:
                prog.completed = True
                prog.completed_at = prog.completed_at or datetime.now(UTC)
            await session.flush()
        if done:
            completed += 1
            earned += int(task.points)
        items.append(
            {
                "id": task.id,
                "slug": task.slug,
                "title": task.title,
                "description": task.description,
                "category": task.category,
                "points": task.points,
                "window_id": task.window_id,
                "auto_check": task.auto_check,
                "completed": done,
                "completed_at": prog.completed_at.isoformat() if prog and prog.completed_at else None,
            }
        )

    return {
        "character_id": character_id,
        "tasks": items,
        "completed": completed,
        "total": len(items),
        "points_earned": earned,
        "points_total": total_points,
        "progress_pct": round(100.0 * completed / len(items), 1) if items else 0.0,
        "achievements": [
            {"slug": "first_steps", "title": "First Steps", "unlocked": completed >= 1},
            {"slug": "half_way", "title": "Halfway There", "unlocked": completed >= max(1, len(items) // 2)},
            {"slug": "graduate", "title": "Onboarding Graduate", "unlocked": completed >= len(items) and len(items) > 0},
            {"slug": "tool_user", "title": "Tool Explorer", "unlocked": any(
                t["completed"] and t["category"] == "tools" for t in items
            )},
        ],
    }


async def complete_onboarding_task(
    session: AsyncSession,
    *,
    character_id: int,
    character_name: str,
    task_slug: str,
) -> dict[str, Any]:
    await ensure_onboarding_defaults(session)
    task = await session.scalar(select(OnboardingTask).where(OnboardingTask.slug == task_slug))
    if not task or not task.active:
        return {"error": "unknown_task"}
    prog = await session.scalar(
        select(OnboardingProgress).where(
            OnboardingProgress.character_id == character_id,
            OnboardingProgress.task_id == task.id,
        )
    )
    if not prog:
        prog = OnboardingProgress(
            character_id=character_id,
            character_name=character_name,
            task_id=int(task.id),
        )
        session.add(prog)
    prog.completed = True
    prog.completed_at = datetime.now(UTC)
    prog.character_name = character_name or prog.character_name
    await session.flush()
    return await onboarding_status(session, character_id=character_id, character_name=character_name)


def _score_metric(value: float, min_v: float, target: float) -> float:
    if target <= min_v:
        return 100.0 if value >= target else 0.0
    if value <= min_v:
        return 0.0
    if value >= target:
        return 100.0
    return max(0.0, min(100.0, 100.0 * (value - min_v) / (target - min_v)))


async def admission_rank(
    session: AsyncSession,
    *,
    character_id: int,
    character_name: str = "",
) -> dict[str, Any]:
    await ensure_onboarding_defaults(session)
    cfg = await session.scalar(select(AdmissionConfig).limit(1))
    admit_threshold = float(cfg.admit_threshold if cfg else 60.0)
    review_threshold = float(cfg.review_threshold if cfg else 40.0)

    kpis = (
        await session.scalars(
            select(AdmissionKpi).where(AdmissionKpi.active.is_(True)).order_by(AdmissionKpi.sort_order)
        )
    ).all()

    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    profile = await session.scalar(select(AuditProfile).where(AuditProfile.character_id == character_id))
    skills = (
        await session.scalars(select(CharacterSkillLevel).where(CharacterSkillLevel.character_id == character_id))
    ).all()
    sp = sum(int(s.skillpoints_in_skill or 0) for s in skills)
    if profile and profile.skill_points:
        sp = max(sp, int(profile.skill_points))

    scopes = parse_granted_scopes(user.scopes_json) if user else set()
    from app.audit_scope_constants import DEFAULT_SSO_SCOPES_STRING

    expected = {s.strip() for s in DEFAULT_SSO_SCOPES_STRING.split() if s.strip()}
    scope_frac = (len(scopes & expected) / len(expected)) if expected else 0.0

    onboard = await onboarding_status(session, character_id=character_id, character_name=character_name)
    onboard_frac = (onboard["completed"] / onboard["total"]) if onboard["total"] else 0.0

    assets_isk = float(profile.assets_value_isk or 0) if profile else 0.0

    zkill = await fetch_character_stats(character_id)
    kills = float(zkill.get("ships_destroyed") or 0)
    losses = float(zkill.get("ships_lost") or 0)
    kd = kills / max(losses, 1.0)

    standings_rows = (
        await session.scalars(select(CharacterStanding).where(CharacterStanding.character_id == character_id))
    ).all()
    avg_standing = (
        sum(float(r.standing) for r in standings_rows) / len(standings_rows) if standings_rows else 0.0
    )

    metrics = {
        "sp": float(sp),
        "kills": kills,
        "kd": kd,
        "scopes": scope_frac,
        "onboarding": onboard_frac,
        "assets": assets_isk,
        "standings": avg_standing,
    }

    breakdown: list[dict[str, Any]] = []
    weighted = 0.0
    weight_sum = 0.0
    for kpi in kpis:
        raw = float(metrics.get(kpi.metric_key, 0.0))
        score = _score_metric(raw, float(kpi.min_value), float(kpi.target_value))
        w = float(kpi.weight or 1.0)
        weighted += score * w
        weight_sum += w
        breakdown.append(
            {
                "slug": kpi.slug,
                "label": kpi.label,
                "description": kpi.description,
                "metric_key": kpi.metric_key,
                "raw_value": raw,
                "score": round(score, 1),
                "weight": w,
                "min_value": kpi.min_value,
                "target_value": kpi.target_value,
            }
        )

    total = round(weighted / weight_sum, 1) if weight_sum else 0.0
    if total >= admit_threshold:
        recommendation = "admit"
        recommendation_label = "Recommend admit"
    elif total >= review_threshold:
        recommendation = "review"
        recommendation_label = "Manual review"
    else:
        recommendation = "deny"
        recommendation_label = "Do not admit yet"

    return {
        "character_id": character_id,
        "character_name": character_name or (user.character_name if user else ""),
        "score": total,
        "admit_threshold": admit_threshold,
        "review_threshold": review_threshold,
        "recommendation": recommendation,
        "recommendation_label": recommendation_label,
        "breakdown": breakdown,
        "metrics": metrics,
        "onboarding_progress_pct": onboard["progress_pct"],
    }


async def list_admission_kpis(session: AsyncSession) -> dict[str, Any]:
    await ensure_onboarding_defaults(session)
    cfg = await session.scalar(select(AdmissionConfig).limit(1))
    kpis = (
        await session.scalars(select(AdmissionKpi).order_by(AdmissionKpi.sort_order))
    ).all()
    return {
        "admit_threshold": float(cfg.admit_threshold if cfg else 60.0),
        "review_threshold": float(cfg.review_threshold if cfg else 40.0),
        "kpis": [
            {
                "id": k.id,
                "slug": k.slug,
                "label": k.label,
                "description": k.description,
                "weight": k.weight,
                "metric_key": k.metric_key,
                "min_value": k.min_value,
                "target_value": k.target_value,
                "active": k.active,
                "sort_order": k.sort_order,
            }
            for k in kpis
        ],
    }


async def update_admission_config(
    session: AsyncSession,
    *,
    admit_threshold: float | None = None,
    review_threshold: float | None = None,
    kpi_updates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    await ensure_onboarding_defaults(session)
    cfg = await session.scalar(select(AdmissionConfig).limit(1))
    if not cfg:
        cfg = AdmissionConfig()
        session.add(cfg)
    if admit_threshold is not None:
        cfg.admit_threshold = float(admit_threshold)
    if review_threshold is not None:
        cfg.review_threshold = float(review_threshold)
    for upd in kpi_updates or []:
        kpi = await session.get(AdmissionKpi, int(upd.get("id") or 0))
        if not kpi:
            continue
        if "weight" in upd:
            kpi.weight = float(upd["weight"])
        if "active" in upd:
            kpi.active = bool(upd["active"])
        if "min_value" in upd:
            kpi.min_value = float(upd["min_value"])
        if "target_value" in upd:
            kpi.target_value = float(upd["target_value"])
    await session.flush()
    return await list_admission_kpis(session)
