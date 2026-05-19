"""Grant corp_orders permissions to Django auth groups (Directors, Officers, etc.)."""

import os

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


def _default_groups() -> list[str]:
    raw = os.environ.get("CORP_ORDERS_GRANT_GROUPS", "Directors,Officers").strip()
    return [g.strip() for g in raw.split(",") if g.strip()]


class Command(BaseCommand):
    help = "Grant corp_orders permissions to auth group(s). Default: Directors and Officers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--group",
            action="append",
            dest="groups",
            help="Auth group name (repeat for multiple). Default: Directors + Officers.",
        )

    def handle(self, *args, **options):
        group_names = options["groups"] or _default_groups()
        perms = Permission.objects.filter(
            content_type__app_label="corp_orders",
            codename__in=("create_order", "create_corp_contract", "manage_orders"),
        )
        for group_name in group_names:
            group, created = Group.objects.get_or_create(name=group_name)
            group.permissions.add(*perms)
            state = "created" if created else "updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Granted {perms.count()} corp_orders permission(s) to group "
                    f"{group_name!r} ({state})."
                )
            )
