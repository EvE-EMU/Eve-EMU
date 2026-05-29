"""One-shot Alliance Auth Discord service setup and role sync."""

from __future__ import annotations

from django.apps import apps
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Migrate Discord service tables, grant state permissions, and optionally "
        "sync Discord roles/nicknames for linked Auth users."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--migrate",
            action="store_true",
            help="Run migrate for the discord app before other steps.",
        )
        parser.add_argument(
            "--grant-perms",
            action="store_true",
            default=True,
            help="Grant discord.access_discord on Member/Blue states (default: on).",
        )
        parser.add_argument(
            "--no-grant-perms",
            action="store_false",
            dest="grant_perms",
            help="Skip granting discord.access_discord on states.",
        )
        parser.add_argument(
            "--sync-all",
            action="store_true",
            help="Sync Discord roles (and nicknames) for every activated Discord link.",
        )
        parser.add_argument(
            "--username",
            type=str,
            help="Sync only this Auth username (must have an activated Discord link).",
        )
        parser.add_argument(
            "--queue-bulk",
            action="store_true",
            help="Enqueue allianceauth discord.update_all_groups via Celery instead of sync.",
        )
        parser.add_argument(
            "--diag",
            action="store_true",
            help="Print bot/guild connectivity diagnostics.",
        )

    def handle(self, *args, **options):
        if not apps.is_installed("allianceauth.services.modules.discord"):
            raise CommandError(
                "Discord service app is not installed. Set DISCORD_BOT_TOKEN and "
                "DISCORD_GUILD_ID in .env, rebuild aa-web/aa-worker, and restart."
            )

        from allianceauth.services.modules.discord.app_settings import (
            DISCORD_APP_ID,
            DISCORD_APP_SECRET,
            DISCORD_BOT_TOKEN,
            DISCORD_CALLBACK_URL,
            DISCORD_GUILD_ID,
        )

        self.stdout.write("Discord service configuration:")
        self.stdout.write(f"  DISCORD_GUILD_ID: {'set' if DISCORD_GUILD_ID else 'MISSING'}")
        self.stdout.write(f"  DISCORD_BOT_TOKEN: {'set' if DISCORD_BOT_TOKEN else 'MISSING'}")
        self.stdout.write(f"  DISCORD_APP_ID: {'set' if DISCORD_APP_ID else 'MISSING'}")
        self.stdout.write(f"  DISCORD_APP_SECRET: {'set' if DISCORD_APP_SECRET else 'MISSING'}")
        self.stdout.write(f"  DISCORD_CALLBACK_URL: {DISCORD_CALLBACK_URL or '(empty)'}")

        if options["migrate"]:
            self.stdout.write("Running migrate discord …")
            call_command("migrate", "discord", verbosity=1)

        if options["grant_perms"]:
            from extensions.discord_group_sync import ensure_discord_service_state_permissions

            ensure_discord_service_state_permissions()
            self.stdout.write(self.style.SUCCESS("State permissions applied (Member/Blue)."))

        from allianceauth.services.modules.discord.models import DiscordUser

        linked = DiscordUser.objects.filter(activated__isnull=False).count()
        self.stdout.write(f"Activated Discord links: {linked}")

        if options["diag"]:
            self._run_diag()

        if options["queue_bulk"]:
            from allianceauth.services.modules.discord.tasks import update_all_groups

            update_all_groups.delay()
            self.stdout.write(
                self.style.SUCCESS("Queued discord.update_all_groups on Celery (services queue).")
            )
            return

        usernames: list[str] = []
        if options["username"]:
            usernames = [options["username"]]
        elif options["sync_all"]:
            usernames = list(
                DiscordUser.objects.filter(activated__isnull=False)
                .values_list("user__username", flat=True)
                .order_by("user__username")
            )

        if not usernames:
            self.stdout.write(
                "Nothing to sync. Use --sync-all, --username <name>, or --queue-bulk."
            )
            return

        from allianceauth.services.modules.discord.app_settings import DISCORD_SYNC_NAMES

        ok = skipped = failed = 0
        for name in usernames:
            try:
                user = User.objects.get(username=name)
                discord_user = DiscordUser.objects.get(user=user)
            except (User.DoesNotExist, DiscordUser.DoesNotExist):
                self.stderr.write(self.style.ERROR(f"{name}: no activated Discord link"))
                failed += 1
                continue
            if not discord_user.activated:
                self.stderr.write(self.style.WARNING(f"{name}: Discord link not activated"))
                skipped += 1
                continue
            try:
                roles_ok = discord_user.update_groups()
                nick_ok = True
                if DISCORD_SYNC_NAMES:
                    nick_ok = discord_user.update_nickname()
                if roles_ok is None or nick_ok is None:
                    self.stderr.write(
                        self.style.WARNING(f"{name}: not in guild (uid={discord_user.uid})")
                    )
                    skipped += 1
                elif roles_ok is False or nick_ok is False:
                    self.stderr.write(self.style.ERROR(f"{name}: Discord API update failed"))
                    failed += 1
                else:
                    self.stdout.write(self.style.SUCCESS(f"{name}: roles and nickname synced"))
                    ok += 1
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"{name}: {exc}"))
                failed += 1

        self.stdout.write(f"Done: {ok} ok, {skipped} skipped, {failed} failed")

    def _run_diag(self) -> None:
        import requests

        from allianceauth.services.modules.discord.app_settings import (
            DISCORD_BOT_TOKEN,
            DISCORD_GUILD_ID,
        )

        if not DISCORD_BOT_TOKEN or not DISCORD_GUILD_ID:
            self.stderr.write("Cannot run diag: bot token or guild id missing.")
            return
        headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
        me = requests.get(
            "https://discord.com/api/users/@me", headers=headers, timeout=15
        )
        self.stdout.write(f"Bot API /users/@me: HTTP {me.status_code}")
        if me.ok:
            data = me.json()
            self.stdout.write(f"  bot user: {data.get('username')} id={data.get('id')}")
        guild = requests.get(
            f"https://discord.com/api/guilds/{DISCORD_GUILD_ID}",
            headers=headers,
            timeout=15,
        )
        self.stdout.write(f"Guild lookup: HTTP {guild.status_code}")
        if guild.ok:
            g = guild.json()
            self.stdout.write(f"  guild: {g.get('name')} id={g.get('id')}")
