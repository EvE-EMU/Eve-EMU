"""Sanitize MediaWiki HTML into Photon-era EMUMS markup."""

from __future__ import annotations

import re
from html import unescape

_RE_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_RE_MW_WRAPPER = re.compile(
    r'<div class="mw-content-ltr mw-parser-output"[^>]*>(.*)</div>\s*$',
    re.DOTALL | re.IGNORECASE,
)
_RE_REDIRECT = re.compile(
    r'class="redirectText"[^>]*>.*?title="([^"]+)"',
    re.DOTALL | re.IGNORECASE,
)
_RE_TYPE_ID = re.compile(
    r"types/(\d+)/render|eve-showinfo__id\">ID\s*(\d+)|#eveshowinfo:type\|(\d+)\|",
    re.IGNORECASE,
)
_RE_WIKI_HREF = re.compile(
    r'href="(?:https?://[^/]+)?(?:/index\.php/|/wiki/)?([^"#?]+)"',
    re.IGNORECASE,
)
_RE_SNIPPET_MARKUP = re.compile(r"<[^>]+>")
_RE_EVE_TYPE = re.compile(r"#eveshowinfo:type\|(\d+)\|", re.IGNORECASE)


def extract_type_id(*sources: str) -> int | None:
    for src in sources:
        if not src:
            continue
        for match in _RE_TYPE_ID.finditer(src):
            for g in match.groups():
                if g:
                    return int(g)
        m = _RE_EVE_TYPE.search(src)
        if m:
            return int(m.group(1))
    return None


def wiki_title_for_type(type_id: int) -> str:
    return f"SDE/Types/{type_id}"


def wiki_category_from_title(title: str) -> str:
    """Classify wiki pages for Knowledge browser filters."""
    t = (title or "").strip()
    if t == "SDE/Types" or t.startswith("SDE/Types/"):
        return "types"
    if t == "SDE/Corporations" or t.startswith("SDE/Corporations/"):
        return "corporations"
    if t == "SDE/Alliances" or t.startswith("SDE/Alliances/"):
        return "alliances"
    if t.startswith("SDE/"):
        return "sde"
    return "guides"


def clean_snippet(snippet: str) -> str:
    text = _RE_SNIPPET_MARKUP.sub("", unescape(snippet or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_wiki_title(raw: str) -> str:
    title = unescape(raw).strip().replace("_", " ")
    if title.startswith("/"):
        title = title.lstrip("/")
    return title


def _rewrite_links(html: str) -> tuple[str, list[dict]]:
    links: list[dict] = []

    def repl(match: re.Match[str]) -> str:
        raw = match.group(1)
        title = _normalize_wiki_title(raw)
        type_id = extract_type_id(title)
        links.append({"title": title, "type_id": type_id})
        if type_id:
            return f'data-wiki-title="{title}" data-type-id="{type_id}" href="#" class="eve-wiki-link eve-wiki-type-link"'
        return f'data-wiki-title="{title}" href="#" class="eve-wiki-link"'

    out = _RE_WIKI_HREF.sub(repl, html)
    return out, links


def sanitize_wiki_html(html: str) -> dict:
    """Strip MediaWiki chrome and restyle for EMUMS."""
    if not html:
        return {"html": "", "type_id": None, "links": [], "is_redirect": False, "redirect_title": None}

    body = _RE_COMMENT.sub("", html).strip()
    wrap = _RE_MW_WRAPPER.search(body)
    if wrap:
        body = wrap.group(1).strip()

    redirect_title = None
    is_redirect = "redirectMsg" in body or "redirectText" in body
    if is_redirect:
        m = _RE_REDIRECT.search(body)
        if m:
            redirect_title = _normalize_wiki_title(m.group(1))

    body, links = _rewrite_links(body)
    type_id = extract_type_id(body)

    # Remove inline MediaWiki / Eve wiki theme classes that clash with EMUMS shell
    body = re.sub(r'\sclass="mw-[^"]*"', "", body)
    body = re.sub(r'\slang="[^"]*"', "", body)
    body = re.sub(r'\sdir="[^"]*"', "", body)

    return {
        "html": body,
        "type_id": type_id,
        "links": links,
        "is_redirect": is_redirect,
        "redirect_title": redirect_title,
    }
