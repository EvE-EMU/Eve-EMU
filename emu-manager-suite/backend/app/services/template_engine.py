"""Jinja2 template rendering for message templates."""

from __future__ import annotations

import json

from jinja2 import Environment, BaseLoader, StrictUndefined

from app.models import MessageTemplate

_env = Environment(loader=BaseLoader(), undefined=StrictUndefined, autoescape=False)


def render_template(tmpl: MessageTemplate, variables: dict) -> tuple[str, str]:
    subject = _env.from_string(tmpl.subject or "").render(**variables)
    body = _env.from_string(tmpl.body or "").render(**variables)
    return subject, body


def parse_variables(tmpl: MessageTemplate) -> list[str]:
    try:
        raw = json.loads(tmpl.variables_json or "[]")
        return [str(x) for x in raw]
    except json.JSONDecodeError:
        return []
