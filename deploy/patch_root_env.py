"""Fill missing secrets in the repository root ``.env`` (idempotent)."""

from __future__ import annotations

import re
import secrets
from pathlib import Path


def _fernet_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


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
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    if not env_path.is_file():
        raise SystemExit(f"Missing {env_path} — copy from .env.example first.")

    text = env_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    changed = False
    data = {m.group(1): m.group(2) for line in lines if (m := re.match(r"^([A-Z0-9_]+)=(.*)$", line))}

    if not (data.get("AA_DJANGO_SECRET_KEY") or "").strip():
        lines = _set_or_replace(lines, "AA_DJANGO_SECRET_KEY", secrets.token_urlsafe(50))
        changed = True

    if not (data.get("CORE_TOKEN_ENCRYPTION_KEY") or "").strip():
        try:
            fkey = _fernet_key()
        except ImportError:
            print(
                "cryptography is not installed; skipping CORE_TOKEN_ENCRYPTION_KEY. "
                "Install it (`pip install cryptography`) or set CORE_TOKEN_ENCRYPTION_KEY manually."
            )
        else:
            lines = _set_or_replace(lines, "CORE_TOKEN_ENCRYPTION_KEY", fkey)
            changed = True

    if changed:
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("Updated .env with generated secrets (AA_DJANGO_SECRET_KEY and/or CORE_TOKEN_ENCRYPTION_KEY).")
    else:
        print("No secret placeholders to fill (AA_DJANGO_SECRET_KEY and CORE_TOKEN_ENCRYPTION_KEY already set).")


if __name__ == "__main__":
    main()
