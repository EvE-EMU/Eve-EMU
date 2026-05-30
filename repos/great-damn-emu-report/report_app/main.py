"""The Great Damn EMU Report — multi-AA forwarder API."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Header, Request
from pydantic import BaseModel, Field

from report_app.config import settings
from report_app.connections import (
    AaLink,
    delete_link,
    get_link,
    list_links,
    test_link,
    to_public,
    upsert_link,
)
from report_app.bridge import sync_export, test_bridge
from report_app.esi import esi_get
from report_app.history import init_db, query_events
from report_app.ingest import ingest_webhook

app = FastAPI(
    title="The Great Damn EMU Report",
    description=(
        "Reporting across multiple Alliance Auth 5 instances via "
        "aa-esi-forwarder (external links supported)."
    ),
    version="0.3.0",
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


def require_admin(x_report_admin_key: str | None = Header(default=None)) -> None:
    key = (settings.admin_api_key or "").strip()
    if not key:
        raise HTTPException(503, "admin API disabled (set REPORT_ADMIN_API_KEY)")
    if (x_report_admin_key or "").strip() != key:
        raise HTTPException(403, "forbidden")


@app.get("/health")
def health() -> dict[str, Any]:
    links = list_links()
    return {
        "status": "ok",
        "links": len(links),
        "public_base_url": settings.public_base_url,
    }


@app.get("/v1/links")
def links_list() -> dict[str, Any]:
    return {"links": [to_public(l) for l in list_links()]}


class LinkCreate(BaseModel):
    id: str = Field(..., examples=["allied-corp"])
    label: str
    forwarder_url: str = Field(..., examples=["https://auth.their-alliance.com"])
    secret: str = Field(..., description="API key from their AA forwarder admin")
    default_token_id: int = 0
    enabled: bool = True


@app.post("/v1/admin/links", dependencies=[Depends(require_admin)])
def admin_add_link(body: LinkCreate) -> dict[str, Any]:
    try:
        link = upsert_link(AaLink.model_validate(body.model_dump()))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"link": to_public(link)}


@app.delete("/v1/admin/links/{link_id}", dependencies=[Depends(require_admin)])
def admin_remove_link(link_id: str) -> dict[str, Any]:
    if not delete_link(link_id):
        raise HTTPException(404, "link not found")
    return {"deleted": link_id}


@app.post("/v1/links/{link_id}/test")
def link_test(link_id: str) -> dict[str, Any]:
    link = get_link(link_id)
    if link is None:
        raise HTTPException(404, "link not found")
    out: dict[str, Any] = {"link_id": link_id}
    try:
        out["forwarder"] = test_link(link)
    except Exception as exc:  # noqa: BLE001
        out["forwarder_error"] = str(exc)
    try:
        out["report_bridge"] = test_bridge(link)
    except Exception as exc:  # noqa: BLE001
        out["report_bridge_error"] = str(exc)
    if "forwarder" not in out and "report_bridge" not in out:
        raise HTTPException(502, out)
    return out


@app.post("/v1/ingest/{link_id}")
async def webhook_ingest(link_id: str, request: Request) -> dict[str, Any]:
    """Receive signed webhooks from aa-report-bridge on that AA instance."""
    return await ingest_webhook(link_id, request)


@app.get("/v1/links/{link_id}/history")
def link_history(link_id: str, model: str | None = None, since: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    _resolve_link(link_id)
    return query_events(link_id, model=model, since=since, limit=limit, offset=offset)


class ExportSyncRequest(BaseModel):
    resource: str = Field(..., examples=["auth.user"])
    page_size: int = Field(default=500, ge=1, le=2000)
    since: str | None = Field(default=None, description="ISO-8601; only rows changed since")


@app.post("/v1/links/{link_id}/sync/export")
def link_export_sync(link_id: str, req: ExportSyncRequest) -> dict[str, Any]:
    _resolve_link(link_id)
    try:
        return sync_export(
            link_id,
            req.resource,
            page_size=req.page_size,
            since_iso=req.since,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"export failed: {exc}") from exc


def _resolve_link(link_id: str) -> str:
    if get_link(link_id) is None:
        raise HTTPException(404, f"unknown link {link_id!r}")
    return link_id


@app.get("/v1/links/{link_id}/character/{character_id}")
def character_sheet(link_id: str, character_id: int) -> dict[str, Any]:
    _resolve_link(link_id)
    try:
        status, body, _ = esi_get(link_id, f"characters/{character_id}/")
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    if status != 200:
        raise HTTPException(status, detail=body)
    return {"link_id": link_id, **body}


@app.get("/v1/links/{link_id}/character/{character_id}/assets")
def character_assets(link_id: str, character_id: int) -> dict[str, Any]:
    _resolve_link(link_id)
    try:
        status, body, meta = esi_get(link_id, f"characters/{character_id}/assets/")
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    if status != 200:
        raise HTTPException(status, detail=body)
    items = body if isinstance(body, list) else []
    return {
        "link_id": link_id,
        "character_id": character_id,
        "item_count": len(items),
        "items": items[:50],
        "truncated": len(items) > 50,
        "esi_pages": meta.get("X-Pages"),
    }


class CorpSnapshotRequest(BaseModel):
    corporation_id: int
    include_wallets: bool = False
    token_id: int | None = None


@app.post("/v1/links/{link_id}/reports/corp-snapshot")
def corp_snapshot(link_id: str, req: CorpSnapshotRequest) -> dict[str, Any]:
    _resolve_link(link_id)
    try:
        status, corp, _ = esi_get(
            link_id,
            f"corporations/{req.corporation_id}/",
            token_id=req.token_id,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    if status != 200:
        raise HTTPException(status, detail=corp)
    out: dict[str, Any] = {
        "link_id": link_id,
        "corporation_id": req.corporation_id,
        "name": corp.get("name"),
        "member_count": corp.get("member_count"),
        "ticker": corp.get("ticker"),
        "generated_by": "great-damn-emu-report",
    }
    if req.include_wallets:
        w_status, wallets, _ = esi_get(
            link_id,
            f"corporations/{req.corporation_id}/wallets/",
            token_id=req.token_id,
        )
        if w_status == 200:
            out["wallets"] = wallets
        else:
            out["wallets_error"] = wallets
    return out
