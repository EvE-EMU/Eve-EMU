"""Export AA states/groups vs Django permissions (run via manage.py shell)."""
from __future__ import annotations

import csv
import io
import sys

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from allianceauth.authentication.models import State

try:
    from allianceauth.groupmanagement.models import AuthGroup
except ImportError:
    AuthGroup = None


def _collect_entities():
    """Return list of (kind, name, permission_set)."""
    entities: list[tuple[str, str, set[str]]] = []

    for state in State.objects.prefetch_related("permissions").order_by("-priority"):
        perms = {
            f"{p.content_type.app_label}.{p.codename}"
            for p in state.permissions.all()
        }
        entities.append(("State", state.name, perms))

    for group in Group.objects.prefetch_related("permissions").order_by("name"):
        perms = {
            f"{p.content_type.app_label}.{p.codename}"
            for p in group.permissions.all()
        }
        entities.append(("Group", group.name, perms))

    # AuthGroup uses the same Django Group permissions; skip duplicate columns unless --authgroups.
    return entities


def _collect_authgroup_entities() -> list[tuple[str, str, set[str]]]:
    entities: list[tuple[str, str, set[str]]] = []
    if AuthGroup is None:
        return entities
    for ag in AuthGroup.objects.select_related("group").prefetch_related(
        "group__permissions", "states"
    ).order_by("group__name"):
        g = ag.group
        perms = {
            f"{p.content_type.app_label}.{p.codename}" for p in g.permissions.all()
        }
        states = ", ".join(s.name for s in ag.states.all()) or "any state"
        entities.append(("AuthGroup", f"{g.name} (states: {states})", perms))
    return entities


def _is_matrix_permission(codename: str) -> bool:
    """User-facing permissions (app access), not Django model CRUD."""
    if codename.startswith(("add_", "change_", "delete_", "view_")):
        return False
    return True


def _permission_catalog(
    entities: list[tuple[str, str, set[str]]], *, include_all_assigned: bool = False
) -> list[str]:
    """Permissions for the matrix rows."""
    assigned: set[str] = set()
    for _, _, perms in entities:
        assigned |= perms

    if include_all_assigned:
        return sorted(assigned)

    filtered = {p for p in assigned if _is_matrix_permission(p.split(".", 1)[-1])}

    access = Permission.objects.filter(codename__startswith="access_").select_related(
        "content_type"
    )
    for p in access:
        label = f"{p.content_type.app_label}.{p.codename}"
        if _is_matrix_permission(p.codename):
            filtered.add(label)

    return sorted(filtered)


def to_csv(entities, catalog) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    header = ["Permission"] + [f"{kind}: {name}" for kind, name, _ in entities]
    w.writerow(header)
    for perm in catalog:
        row = [perm]
        for _, _, perms in entities:
            row.append("Yes" if perm in perms else "")
        w.writerow(row)
    return buf.getvalue()


def to_markdown(entities, catalog) -> str:
    cols = [f"{kind}: {name}" for kind, name, _ in entities]
    lines = [
        "# Alliance Auth permissions matrix",
        "",
        "Generated from live DB (States, Django Groups, AuthGroups).",
        "Yes = permission granted on that state/group.",
        "",
    ]
    if not entities:
        lines.append("_No states or groups found._")
        return "\n".join(lines)

    # Markdown table: escape pipes in names
    def esc(s: str) -> str:
        return s.replace("|", "\\|")

    header = "| Permission | " + " | ".join(esc(c) for c in cols) + " |"
    sep = "|---|" + "|".join(["---"] * len(cols)) + "|"
    lines.extend([header, sep])
    for perm in catalog:
        cells = ["Yes" if perm in ent_perms else "" for _, _, ent_perms in entities]
        lines.append("| " + esc(perm) + " | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(
    fmt: str = "markdown",
    full: bool = False,
    authgroups: bool = False,
    out_path: str | None = None,
) -> None:
    entities = _collect_entities()
    if authgroups:
        entities.extend(_collect_authgroup_entities())
    if not entities:
        print("No states or groups in database.", file=sys.stderr)
        return
    catalog = _permission_catalog(entities, include_all_assigned=full)
    text = to_csv(entities, catalog) if fmt == "csv" else to_markdown(entities, catalog)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        print(text)


if __name__ == "__main__":
    fmt = "markdown"
    full = "--full" in sys.argv
    authgroups = "--authgroups" in sys.argv
    out_path = None
    for arg in sys.argv[1:]:
        if arg in ("markdown", "csv"):
            fmt = arg
        elif arg.startswith("--out="):
            out_path = arg.split("=", 1)[1]
    main(fmt, full=full, authgroups=authgroups, out_path=out_path)
