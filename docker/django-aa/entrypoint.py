#!/usr/bin/env python3
"""Container entrypoint: optional Alliance Auth source mount, migrate on web boot, then exec."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_aa = Path("/opt/allianceauth")
if _aa.is_dir():
    for name in ("pyproject.toml", "setup.py", "setup.cfg"):
        if (_aa / name).is_file():
            os.environ["PYTHONPATH"] = f"/opt/allianceauth:{os.environ.get('PYTHONPATH', '')}".rstrip(":")
            break

argv = sys.argv[1:]
if not argv:
    sys.stderr.write("entrypoint: missing command\n")
    sys.exit(2)

_manage = Path("/app/site/manage.py")
if _manage.is_file():
    exe = Path(argv[0]).name
    if exe == "gunicorn":
        env = os.environ.copy()
        env.setdefault("DJANGO_SETTINGS_MODULE", "eve_auth.settings.local")
        cwd = str(_manage.parent)
        subprocess.run(
            [sys.executable, "/app/deploy/aa_docker/repair_indy_hub_migrations.py"],
            cwd=cwd,
            env=env,
            check=False,
        )
        subprocess.run(
            [sys.executable, str(_manage), "migrate", "--noinput"],
            cwd=cwd,
            env=env,
            check=True,
        )
        subprocess.run(
            [sys.executable, str(_manage), "collectstatic", "--noinput"],
            cwd=cwd,
            env=env,
            check=True,
        )
        if os.environ.get("AA_TOP_RUN_ON_BOOT", "1").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        ):
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import django; django.setup(); "
                    "from top_postgres_compat import ensure_top_static_dir, patch_top_for_postgresql; "
                    "ensure_top_static_dir(); patch_top_for_postgresql(); "
                    "from top.tasks import update_aa_top_txt; update_aa_top_txt()",
                ],
                cwd=cwd,
                env=env,
                check=False,
            )
        if os.environ.get("AA_PACKAGE_MONITOR_REFRESH_ON_BOOT", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        ):
            subprocess.run(
                [sys.executable, str(_manage), "packagemonitorcli", "refresh"],
                cwd=cwd,
                env=env,
                check=False,
            )

os.execvp(argv[0], argv)
