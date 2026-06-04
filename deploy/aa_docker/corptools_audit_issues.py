"""Human-readable CharacterAudit inactive reasons for account list tooltips."""

from __future__ import annotations

import datetime

from django.utils import timezone

from corptools import app_settings
from corptools.models.audits import CharacterAudit, CorptoolsConfiguration, check_date


def _stale_label(label: str, last_update, time_ref) -> str | None:
    if check_date(last_update, time_ref):
        return None
    if last_update is None:
        return f"{label}: never synced"
    age = timezone.now() - last_update
    days = max(age.days, 0)
    if days == 0:
        hours = max(int(age.total_seconds() // 3600), 1)
        return f"{label}: stale ({hours}h ago)"
    return f"{label}: stale ({days}d ago)"


def get_audit_inactive_issues(audit: CharacterAudit) -> list[str]:
    """Mirror CharacterAudit.is_active() checks and return failing modules."""
    time_ref = timezone.now() - datetime.timedelta(
        days=app_settings.CT_CHAR_MAX_INACTIVE_DAYS
    )
    ct_conf = CorptoolsConfiguration.get_solo()
    issues: list[str] = []

    checks: list[tuple[bool, bool, str, str]] = [
        (
            app_settings.CT_CHAR_ACTIVE_IGNORE_CORP_HISTORY,
            ct_conf.disable_update_pub_data,
            "Public Data",
            "last_update_pub_data",
        ),
        (
            app_settings.CT_CHAR_ASSETS_MODULE
            and not app_settings.CT_CHAR_ACTIVE_IGNORE_ASSETS_MODULE,
            ct_conf.disable_update_assets,
            "Assets",
            "last_update_assets",
        ),
        (
            app_settings.CT_CHAR_CLONES_MODULE
            and not app_settings.CT_CHAR_ACTIVE_IGNORE_CLONES_MODULE,
            ct_conf.disable_update_clones,
            "Clones",
            "last_update_clones",
        ),
        (
            app_settings.CT_CHAR_SKILLS_MODULE
            and not app_settings.CT_CHAR_ACTIVE_IGNORE_SKILLS_MODULE,
            ct_conf.disable_update_skills,
            "Skills",
            "last_update_skills",
        ),
        (
            app_settings.CT_CHAR_SKILLS_MODULE
            and not app_settings.CT_CHAR_ACTIVE_IGNORE_SKILLS_MODULE,
            ct_conf.disable_update_skills,
            "Skill Queue",
            "last_update_skill_que",
        ),
        (
            app_settings.CT_CHAR_WALLET_MODULE
            and not app_settings.CT_CHAR_ACTIVE_IGNORE_WALLET_MODULE,
            ct_conf.disable_update_wallet,
            "Wallet",
            "last_update_wallet",
        ),
        (
            app_settings.CT_CHAR_WALLET_MODULE
            and not app_settings.CT_CHAR_ACTIVE_IGNORE_WALLET_MODULE,
            ct_conf.disable_update_wallet,
            "Orders",
            "last_update_orders",
        ),
        (
            app_settings.CT_CHAR_NOTIFICATIONS_MODULE
            and not app_settings.CT_CHAR_ACTIVE_IGNORE_NOTIFICATIONS_MODULE,
            ct_conf.disable_update_notif,
            "Notifications",
            "last_update_notif",
        ),
        (
            app_settings.CT_CHAR_ROLES_MODULE
            and not app_settings.CT_CHAR_ACTIVE_IGNORE_ROLES_MODULE,
            ct_conf.disable_update_roles,
            "Roles",
            "last_update_roles",
        ),
        (
            app_settings.CT_CHAR_MAIL_MODULE
            and not app_settings.CT_CHAR_ACTIVE_IGNORE_MAIL_MODULE,
            ct_conf.disable_update_mails,
            "Mail",
            "last_update_mails",
        ),
        (
            app_settings.CT_CHAR_LOYALTYPOINTS_MODULE
            and not app_settings.CT_CHAR_ACTIVE_IGNORE_LOYALTYPOINTS_MODULE,
            ct_conf.disable_update_loyaltypoints,
            "LP",
            "last_update_loyaltypoints",
        ),
        (
            app_settings.CT_CHAR_MINING_MODULE
            and not app_settings.CT_CHAR_ACTIVE_IGNORE_MINING_MODULE,
            ct_conf.disable_update_mining,
            "Mining",
            "last_update_mining",
        ),
    ]

    for enabled, disabled, label, field in checks:
        if not enabled or disabled:
            continue
        msg = _stale_label(label, getattr(audit, field), time_ref)
        if msg:
            issues.append(msg)

    if not issues:
        issues.append("Audit marked inactive — refresh via Charlink or wait for sync")
    return issues


def character_list_entry(character, audit=None) -> dict:
    if audit is None:
        try:
            audit = character.characteraudit
        except CharacterAudit.DoesNotExist:
            audit = None

    if audit is None:
        return {
            "character": character,
            "active": False,
            "issues": ["Not linked to Character Audit — enable via Charlink"],
        }

    active = bool(audit.active)
    issues = [] if active else get_audit_inactive_issues(audit)
    return {
        "character": character,
        "active": active,
        "issues": issues,
    }
