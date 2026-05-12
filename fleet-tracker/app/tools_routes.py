"""HTML + JSON routes for SRP matrix and doctrine reference pages."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from app.tools_data import get_doctrine_by_slug, load_doctrines, load_srp_matrix

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def _isk_filter(value: object) -> str:
    if value is None:
        return "—"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


_TEMPLATES.env.filters["isk"] = _isk_filter

router = APIRouter(tags=["tools"])


@router.get("/", response_class=HTMLResponse)
async def fleet_home(request: Request) -> HTMLResponse:
    return _TEMPLATES.TemplateResponse(request, "home.html", {"title": "Home"})


@router.get("/tools/srp", response_class=HTMLResponse)
async def tools_srp(request: Request) -> HTMLResponse:
    matrix, err = load_srp_matrix()
    return _TEMPLATES.TemplateResponse(
        request,
        "srp.html",
        {"title": "SRP matrix", "matrix": matrix, "load_error": err},
    )


@router.get("/tools/doctrine", response_class=HTMLResponse)
async def tools_doctrine_list(request: Request) -> HTMLResponse:
    bundle, err = load_doctrines()
    return _TEMPLATES.TemplateResponse(
        request,
        "doctrine_list.html",
        {"title": "Doctrines", "bundle": bundle, "load_error": err},
    )


@router.get("/tools/doctrine/{slug}", response_class=HTMLResponse)
async def tools_doctrine_detail(request: Request, slug: str) -> HTMLResponse:
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=400, detail="Invalid doctrine slug")
    doc, bundle = get_doctrine_by_slug(slug)
    if doc is None:
        raise HTTPException(status_code=404, detail="Doctrine not found")
    return _TEMPLATES.TemplateResponse(
        request,
        "doctrine_detail.html",
        {"title": doc.display_name, "doc": doc, "bundle_intro": bundle.intro},
    )


@router.get("/api/tools/srp.json")
async def api_srp_json() -> dict:
    matrix, _ = load_srp_matrix()
    return matrix.model_dump(mode="json")


@router.get("/api/tools/doctrines.json")
async def api_doctrines_json() -> dict:
    bundle, _ = load_doctrines()
    return bundle.model_dump(mode="json")


@router.get("/api/tools/doctrines/{slug}.json")
async def api_doctrine_one_json(slug: str) -> dict:
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=400, detail="Invalid doctrine slug")
    doc, bundle = get_doctrine_by_slug(slug)
    if doc is None:
        raise HTTPException(status_code=404, detail="Doctrine not found")
    return {"intro": bundle.intro, "doctrine": doc.model_dump(mode="json")}
