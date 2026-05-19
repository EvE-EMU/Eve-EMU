"""Markdown builders for SDE wiki pages."""

from __future__ import annotations

from html import escape


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def md_link(path: str, label: str) -> str:
    return f"[{escape(label, quote=False)}]({path})"


def field_table(fields: dict[str, str | int | float | bool | None]) -> str:
    rows = []
    for key, val in fields.items():
        if val is None or val == "":
            continue
        rows.append([f"**{key}**", str(val)])
    if not rows:
        return "_No data._"
    return md_table(["Field", "Value"], rows)


def wiki_path(*parts: str | int) -> str:
    return "/".join(str(p) for p in parts)
