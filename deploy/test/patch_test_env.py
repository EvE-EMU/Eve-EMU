"""Ensure `.env.test` has secrets (idempotent)."""

from __future__ import annotations

import re
import secrets
import sys
from pathlib import Path


def _set_or_replace(lines: list[str], key: str, value: str) -> list[str]:
    pat = re.compile(rf"^{re.escape(key)}=.*$")
    out: list[str] = []
    replaced = False
    for line in lines:
        if pat.match(line):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
    return out


def main() -> None:
    root = Path(__file__).resolve().parent.parent.parent
    env_path = root / ".env.test"
    if not env_path.is_file():
        example = root / ".env.test.example"
        if not example.is_file():
            raise SystemExit("Missing .env.test.example")
        env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")

    lines = env_path.read_text(encoding="utf-8").splitlines()

    def _value(key: str) -> str | None:
        pat = re.compile(rf"^{re.escape(key)}=(.*)$")
        for line in lines:
            m = pat.match(line)
            if m and m.group(1).strip():
                return m.group(1).strip()
        return None

    prod_path = root / ".env"
    prod_lines: list[str] = []
    if prod_path.is_file():
        prod_lines = prod_path.read_text(encoding="utf-8").splitlines()

    def _prod_value(key: str) -> str | None:
        pat = re.compile(rf"^{re.escape(key)}=(.*)$")
        for line in prod_lines:
            m = pat.match(line)
            if m and m.group(1).strip():
                return m.group(1).strip()
        return None

    for key in ("AA_DJANGO_SECRET_KEY", "POSTGRES_PASSWORD"):
        if not _value(key):
            lines = _set_or_replace(lines, key, secrets.token_urlsafe(48))

    for key in (
        "POSTGRES_PUBLISH_PORT",
        "REDIS_PUBLISH_PORT",
        "CORE_API_PUBLISH_PORT",
        "CORE_WEB_PUBLISH_PORT",
    ):
        if not _value(key):
            defaults = {
                "POSTGRES_PUBLISH_PORT": "15432",
                "REDIS_PUBLISH_PORT": "16379",
                "CORE_API_PUBLISH_PORT": "18000",
                "CORE_WEB_PUBLISH_PORT": "13000",
            }
            lines = _set_or_replace(lines, key, defaults[key])

    for key in ("ESI_CLIENT_ID", "ESI_CLIENT_SECRET", "DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID"):
        if not _value(key):
            prod_val = _prod_value(key)
            if prod_val:
                lines = _set_or_replace(lines, key, prod_val)

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
    sys.exit(0)
