"""HTTP client for AA5 ``aa-report-bridge`` export API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterator

import httpx


class ReportBridgeClient:
    def __init__(
        self,
        *,
        base_url: str,
        secret: str,
        timeout: float = 120.0,
        user_agent: str = "ReportBridgeClient/1.0",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret.strip()
        self.timeout = timeout
        self.user_agent = user_agent

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.secret}",
            "X-Report-Bridge-Secret": self.secret,
            "User-Agent": self.user_agent,
        }

    def ping(self) -> dict[str, Any]:
        url = f"{self.base_url}/internal/report-bridge/v1/health/"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def list_resources(self) -> dict[str, Any]:
        url = f"{self.base_url}/internal/report-bridge/v1/resources/"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def export_page(
        self,
        resource: str,
        *,
        limit: int = 500,
        offset: int = 0,
        since: datetime | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "limit": str(limit),
            "offset": str(offset),
        }
        if since is not None:
            params["since"] = since.isoformat()
        url = f"{self.base_url}/internal/report-bridge/v1/export/{resource}/"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def export_all(
        self,
        resource: str,
        *,
        page_size: int = 500,
        since: datetime | None = None,
    ) -> Iterator[dict[str, Any]]:
        offset = 0
        while True:
            page = self.export_page(
                resource, limit=page_size, offset=offset, since=since
            )
            items = page.get("items") or []
            for item in items:
                yield item
            total = int(page.get("total") or 0)
            offset += page_size
            if offset >= total or not items:
                break
