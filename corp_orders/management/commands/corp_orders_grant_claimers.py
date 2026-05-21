"""Grant claim_fulfillment to groups that fill corp stock orders (e.g. Members, Logistics)."""

import os

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


def _default_groups() -> list[str]:
    raw = os.environ.get("CORP_ORDERS_CLAIM_GROUPS", "Members,Directors,Officers").strip()
    return [g.strip() for g in raw.split(",") if g.strip()]


class Command(BaseCommand):
    help = (
        "Grant corp_orders.claim_fulfillment to auth group(s). "
        "Default: Members, Directors, Officers (override with CORP_ORDERS_CLAIM_GROUPS)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--group",
            action="append",
            dest="groups",
            help="Auth group name (repeat for multiple).",
        )

    def handle(self, *args, **options):
        group_names = options["groups"] or _default_groups()
        perms = Permission.objects.filter(
            content_type__app_label="corp_orders",
            codename="claim_fulfillment",
        )
        if not perms.exists():
            self.stderr.write(
                self.style.ERROR(
                    "Permission claim_fulfillment not found — run migrate corp_orders first."
                )
            )
            return
        for group_name in group_names:
            group, created = Group.objects.get_or_create(name=group_name)
            group.permissions.add(*perms)
            state = "created" if created else "updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Granted claim_fulfillment to group {group_name!r} ({state})."
                )
            )
