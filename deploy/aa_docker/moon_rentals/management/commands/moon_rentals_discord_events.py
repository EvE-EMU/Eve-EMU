"""Create Discord scheduled events for moon pops from a schedule file."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Create Discord guild scheduled events (voice channel) for moon pops. "
        "Uses deploy/aa_docker/scripts/moon_pop_discord_scheduled_events.py"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            nargs="?",
            default="",
            help="Schedule file (default: scripts/data/moon_pops_jun_jul_2026.txt)",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Create events on Discord (default: dry-run)",
        )
        parser.add_argument(
            "--voice-channel",
            default="",
            help="Voice channel name substring (default: corp 2 or MOON_POP_DISCORD_VOICE_CHANNEL)",
        )

    def handle(self, *args, **options):
        import subprocess
        import sys
        from pathlib import Path

        script = (
            Path(__file__).resolve().parents[3]
            / "scripts"
            / "moon_pop_discord_scheduled_events.py"
        )
        data = options["file"].strip()
        if not data:
            data = str(script.parent / "data" / "moon_pops_jun_jul_2026.txt")

        cmd = [sys.executable, str(script), "--file", data]
        if options["apply"]:
            cmd.append("--apply")
        else:
            cmd.append("--dry-run")
        if options["voice_channel"]:
            cmd.extend(["--voice-channel", options["voice_channel"]])

        self.stdout.write("Running: " + " ".join(cmd))
        raise SystemExit(subprocess.call(cmd))
