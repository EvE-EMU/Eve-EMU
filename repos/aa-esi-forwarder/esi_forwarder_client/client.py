"""HTTP client for AA5 ``aa-esi-forwarder`` internal API."""

from __future__ import annotations

import json
from typing import Any

import httpx


class EsiForwarderClient:
    def __init__(
        self,
        *,
        base_url: str,
        secret: str,
        timeout: float = 60.0,
        user_agent: str = "EsiForwarderClient/1.0",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret.strip()
        self.timeout = timeout
        self.user_agent = user_agent

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.secret}",
            "X-Esi-Forwarder-Secret": self.secret,
            "User-Agent": self.user_agent,
        }

    def ping(self) -> dict[str, Any]:
        """Verify URL + API key (for linking external AA5 instances)."""
        url = f"{self.base_url}/internal/esi-forwarder/v1/health/"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def get_access_token(self, *, token_id: int | None = None) -> dict[str, Any]:
        params = {}
        if token_id is not None:
            params["token_id"] = str(token_id)
        url = f"{self.base_url}/internal/esi-forwarder/v1/token/"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def esi_request(
        self,
        method: str,
        esi_path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        token_id: int | None = None,
    ) -> tuple[int, Any, dict[str, str]]:
        """Call ESI via AA proxy. ``esi_path`` is without ``/latest/`` prefix."""
        path = esi_path.lstrip("/")
        q = dict(params or {})
        if token_id is not None:
            q["token_id"] = str(token_id)
        url = f"{self.base_url}/internal/esi-forwarder/v1/proxy/{path}"
        headers = self._headers()
        content = None
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            content = json.dumps(json_body)
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.request(
                method.upper(),
                url,
                headers=headers,
                params=q,
                content=content,
            )
        meta = {
            k: v
            for k, v in resp.headers.items()
            if k.lower().startswith("x-") or k in ("ETag", "Last-Modified")
        }
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return resp.status_code, body, meta

    def esi_get(
        self,
        esi_path: str,
        *,
        params: dict[str, Any] | None = None,
        token_id: int | None = None,
    ) -> tuple[int, Any, dict[str, str]]:
        return self.esi_request(
            "GET", esi_path, params=params, token_id=token_id
        )
