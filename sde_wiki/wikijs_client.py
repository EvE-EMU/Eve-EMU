"""Wiki.js GraphQL client for SDE import and theme configuration."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable, Iterable

from django.conf import settings
from graphqlclient import GraphQLClient

LOCALE = "en"
EDITOR = "markdown"

_PAGE_TREE = """
query PageTree($path: String!, $locale: String!) {
  pages {
    tree(path: $path, parent: null, mode: ALL, locale: $locale, includeAncestors: true) {
      path
      pageId
    }
  }
}
"""

_LIST_PAGES = """
query ListPages($locale: String!, $limit: Int!) {
  pages {
    list(locale: $locale, limit: $limit, orderBy: PATH, orderByDirection: ASC) {
      id
      path
    }
  }
}
"""

_PAGE_BY_PATH = """
query PageByPath($path: String!, $locale: String!) {
  pages {
    singleByPath(path: $path, locale: $locale) {
      id
      path
    }
  }
}
"""

_DELETE_PAGE = """
mutation DeletePage($id: Int!) {
  pages {
    delete(id: $id) {
      responseResult { succeeded message errorCode }
    }
  }
}
"""

_CREATE_PAGE = """
mutation CreatePage(
  $content: String!
  $description: String!
  $editor: String!
  $isPublished: Boolean!
  $isPrivate: Boolean!
  $locale: String!
  $path: String!
  $tags: [String]!
  $title: String!
) {
  pages {
    create(
      content: $content
      description: $description
      editor: $editor
      isPublished: $isPublished
      isPrivate: $isPrivate
      locale: $locale
      path: $path
      tags: $tags
      title: $title
    ) {
      responseResult { succeeded message errorCode }
      page { id path title }
    }
  }
}
"""

_UPDATE_PAGE = """
mutation UpdatePage(
  $id: Int!
  $content: String!
  $description: String!
  $editor: String!
  $isPublished: Boolean!
  $locale: String!
  $path: String!
  $tags: [String]!
  $title: String!
) {
  pages {
    update(
      id: $id
      content: $content
      description: $description
      editor: $editor
      isPublished: $isPublished
      locale: $locale
      path: $path
      tags: $tags
      title: $title
    ) {
      responseResult { succeeded message errorCode }
      page { id path title }
    }
  }
}
"""

_FLUSH_CACHE = """
mutation FlushCache {
  pages {
    flushCache {
      responseResult { succeeded message }
    }
  }
}
"""

_REBUILD_TREE = """
mutation RebuildTree {
  pages {
    rebuildTree {
      responseResult { succeeded message errorCode }
    }
  }
}
"""

_RENDER_PAGE = """
mutation RenderPage($id: Int!) {
  pages {
    render(id: $id) {
      responseResult { succeeded message errorCode }
    }
  }
}
"""

_TREE_RACE_MARKERS = ("rebuild-tree", "pagetree", "page tree", "pagetree_parent")

_THEMING_CONFIG = """
query ThemingConfig {
  theming {
    config {
      theme
      iconset
      darkMode
      tocPosition
      injectCSS
      injectHead
      injectBody
    }
  }
}
"""

_SET_THEMING = """
mutation SetTheming(
  $theme: String!
  $iconset: String!
  $darkMode: Boolean!
  $tocPosition: String
  $injectCSS: String
  $injectHead: String
  $injectBody: String
) {
  theming {
    setConfig(
      theme: $theme
      iconset: $iconset
      darkMode: $darkMode
      tocPosition: $tocPosition
      injectCSS: $injectCSS
      injectHead: $injectHead
      injectBody: $injectBody
    ) {
      responseResult { succeeded message errorCode }
    }
  }
}
"""


class WikiJsClientError(RuntimeError):
    pass


def _is_tree_race_error(message: str) -> bool:
    lower = message.lower()
    return any(marker in lower for marker in _TREE_RACE_MARKERS)


def _is_duplicate_path_error(message: str, error_code: str | int | None) -> bool:
    if str(error_code) == "6002":
        return True
    return "already exists at the same path" in message.lower()


class WikiJsClient:
    """GraphQL client with path index; writes are serialized for Wiki.js tree safety."""

    def __init__(
        self,
        throttle_ms: int = 0,
        *,
        render_after_write: bool = False,
        tree_settle_ms: int = 0,
        parallel_writes: bool = False,
        path_index: dict[str, int] | None = None,
        path_lock: threading.Lock | None = None,
        write_lock: threading.Lock | None = None,
    ):
        api_url = getattr(settings, "WIKIJS_API_URL", "") or ""
        api_key = getattr(settings, "WIKIJS_API_KEY", "") or ""
        if not api_url or not api_key:
            raise WikiJsClientError(
                "WIKIJS_API_URL and WIKIJS_API_KEY must be set (see docs/WIKIJS.md)."
            )
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._client = self._new_graphql_client()
        self._throttle_ms = max(0, throttle_ms)
        self.render_after_write = render_after_write
        self.tree_settle_ms = max(0, tree_settle_ms)
        self.parallel_writes = parallel_writes
        self._path_to_id: dict[str, int] = path_index if path_index is not None else {}
        self._path_lock = path_lock or threading.Lock()
        self._write_lock = (
            threading.Lock()
            if parallel_writes and write_lock is None
            else (write_lock or threading.Lock())
        )

    def _new_graphql_client(self) -> GraphQLClient:
        client = GraphQLClient(f"{self._api_url}/graphql")
        client.inject_token(f"Bearer {self._api_key}")
        return client

    def clone(self) -> WikiJsClient:
        """Thread-local client sharing the same path index."""
        return WikiJsClient(
            self._throttle_ms,
            render_after_write=self.render_after_write,
            tree_settle_ms=self.tree_settle_ms,
            path_index=self._path_to_id,
            path_lock=self._path_lock,
            write_lock=self._write_lock,
        )

    def _execute(self, query: str, variables: dict | None = None) -> dict:
        raw = self._client.execute(query, variables=variables or {})
        data = json.loads(raw)
        if data.get("errors"):
            raise WikiJsClientError(str(data["errors"]))
        if self._throttle_ms:
            time.sleep(self._throttle_ms / 1000.0)
        return data.get("data") or {}

    def _path_under_prefix(self, path: str, prefix: str) -> bool:
        return path == prefix or path.startswith(f"{prefix}/")

    def preload_paths(self, prefix: str = "sde", locale: str = LOCALE) -> int:
        """Load existing page paths (bulk list + tree) so skip-existing needs no per-page GET."""
        prefix = prefix.strip("/")

        def _merge(path: str, page_id: int) -> None:
            if path and page_id and self._path_under_prefix(path, prefix):
                with self._path_lock:
                    self._path_to_id[path] = page_id

        try:
            data = self._execute(_LIST_PAGES, {"locale": locale, "limit": 50000})
            for item in data.get("pages", {}).get("list") or []:
                path = (item.get("path") or "").strip("/")
                if item.get("id"):
                    _merge(path, int(item["id"]))
        except WikiJsClientError:
            pass

        try:
            data = self._execute(_PAGE_TREE, {"path": prefix, "locale": locale})
            for item in data.get("pages", {}).get("tree") or []:
                path = (item.get("path") or "").strip("/")
                page_id = item.get("pageId")
                if page_id:
                    _merge(path, int(page_id))
        except WikiJsClientError:
            pass

        with self._path_lock:
            return sum(
                1 for p in self._path_to_id if self._path_under_prefix(p, prefix)
            )

    def resolve_page_id(self, path: str, locale: str = LOCALE) -> int | None:
        path = path.strip("/")
        with self._path_lock:
            cached = self._path_to_id.get(path)
        if cached:
            return cached
        try:
            data = self._execute(_PAGE_BY_PATH, {"path": path, "locale": locale})
            page = (data.get("pages") or {}).get("singleByPath")
            if page and page.get("id"):
                page_id = int(page["id"])
                with self._path_lock:
                    self._path_to_id[path] = page_id
                return page_id
        except WikiJsClientError:
            pass
        return None

    def delete_page(self, page_id: int) -> None:
        with self._write_lock:
            result = self._execute(_DELETE_PAGE, {"id": page_id})
        status = (
            (result.get("pages") or {}).get("delete") or {}
        ).get("responseResult") or {}
        if not status.get("succeeded"):
            raise WikiJsClientError(
                f"delete failed (id={page_id}): {status.get('message')}"
            )

    def purge_paths(
        self,
        prefix: str = "sde",
        locale: str = LOCALE,
        *,
        progress_callback=None,
    ) -> int:
        """Delete all pages under prefix (deepest paths first)."""
        prefix = prefix.strip("/")
        self.preload_paths(prefix, locale=locale)
        with self._path_lock:
            paths = sorted(
                (
                    p
                    for p in self._path_to_id
                    if self._path_under_prefix(p, prefix)
                ),
                key=lambda p: (-p.count("/"), p),
            )
            id_by_path = {p: self._path_to_id[p] for p in paths}

        deleted = 0
        total = len(paths)
        for path in paths:
            page_id = id_by_path.get(path)
            if not page_id:
                continue
            self.delete_page(page_id)
            with self._path_lock:
                self._path_to_id.pop(path, None)
            deleted += 1
            if progress_callback:
                progress_callback(deleted, total, path)

        if deleted:
            try:
                self.rebuild_page_tree()
            except WikiJsClientError:
                pass
            self.flush_wiki_cache()
        return deleted

    def flush_wiki_cache(self) -> None:
        try:
            with self._write_lock:
                self._execute(_FLUSH_CACHE)
        except WikiJsClientError:
            pass

    def rebuild_page_tree(self) -> None:
        """Rebuild Wiki.js page tree once after bulk import (fixes pagetree FK races)."""
        with self._write_lock:
            result = self._execute(_REBUILD_TREE)
        status = result.get("pages", {}).get("rebuildTree", {}).get("responseResult", {})
        if not status.get("succeeded"):
            raise WikiJsClientError(f"rebuildTree failed: {status.get('message')}")

    def render_page(self, page_id: int) -> None:
        """Generate HTML render for a page (required after --via-db bulk insert)."""
        result = self._execute(_RENDER_PAGE, {"id": page_id})
        status = (result.get("pages") or {}).get("render", {}).get("responseResult", {})
        if not status.get("succeeded"):
            raise WikiJsClientError(
                f"render failed for page id={page_id}: {status.get('message')}"
            )

    def render_pages(
        self,
        page_ids: Iterable[int],
        *,
        workers: int = 8,
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> tuple[int, int]:
        """Render many pages in parallel. Returns (ok_count, error_count)."""
        ids = list(page_ids)
        total = len(ids)
        if total == 0:
            return 0, 0
        workers = max(1, min(workers, 16))
        ok = 0
        errors = 0

        def _render_one(page_id: int) -> None:
            worker = self.clone() if workers > 1 else self
            worker.render_page(page_id)

        if workers <= 1:
            for idx, page_id in enumerate(ids, start=1):
                try:
                    _render_one(page_id)
                    ok += 1
                except WikiJsClientError:
                    errors += 1
                if progress_callback:
                    progress_callback(idx, total, page_id)
            return ok, errors

        done = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_render_one, pid): pid for pid in ids}
            for future in as_completed(futures):
                page_id = futures[future]
                done += 1
                try:
                    future.result()
                    ok += 1
                except WikiJsClientError:
                    errors += 1
                if progress_callback:
                    progress_callback(done, total, page_id)
        return ok, errors

    def upsert_page(
        self,
        *,
        path: str,
        title: str,
        content: str,
        description: str = "",
        tags: list[str] | None = None,
        locale: str = LOCALE,
        skip_existing: bool = False,
        dry_run: bool = False,
    ) -> str:
        """Return 'created', 'updated', 'skipped', or 'dry-run'."""
        path = path.strip("/")
        tags = tags or ["sde"]
        description = (description or title)[:250]

        if dry_run:
            return "dry-run"

        with self._path_lock:
            existing_id = self._path_to_id.get(path)

        if existing_id and skip_existing:
            return "skipped"

        variables = {
            "content": content,
            "description": description,
            "editor": EDITOR,
            "isPublished": True,
            "isPrivate": False,
            "locale": locale,
            "path": path,
            "tags": tags,
            "title": title,
        }

        max_attempts = 5
        lock = None if self.parallel_writes else self._write_lock
        lock_ctx = lock if lock is not None else nullcontext()
        with lock_ctx:
            for attempt in range(max_attempts):
                try:
                    if existing_id:
                        variables["id"] = existing_id
                        result = self._execute(_UPDATE_PAGE, variables)
                        block = result.get("pages", {}).get("update", {})
                        action = "updated"
                    else:
                        result = self._execute(_CREATE_PAGE, variables)
                        block = result.get("pages", {}).get("create", {})
                        action = "created"

                    status = block.get("responseResult") or {}
                    if not status.get("succeeded"):
                        message = status.get("message") or ""
                        error_code = status.get("errorCode")
                        if skip_existing and _is_duplicate_path_error(message, error_code):
                            page_id = self.resolve_page_id(path, locale=locale)
                            if page_id:
                                return "skipped"
                        if _is_tree_race_error(message) and attempt + 1 < max_attempts:
                            time.sleep(0.4 * (attempt + 1))
                            continue
                        raise WikiJsClientError(
                            f"{action} failed for {path}: {message} ({error_code})"
                        )

                    page = block.get("page") or {}
                    page_id = page.get("id")
                    if page_id:
                        with self._path_lock:
                            self._path_to_id[path] = int(page_id)

                    if action == "created" and self.tree_settle_ms:
                        time.sleep(self.tree_settle_ms / 1000.0)

                    return action
                except WikiJsClientError as exc:
                    if _is_tree_race_error(str(exc)) and attempt + 1 < max_attempts:
                        time.sleep(0.4 * (attempt + 1))
                        continue
                    raise

        raise WikiJsClientError(f"upsert failed for {path} after {max_attempts} attempts")

    def get_theming_config(self) -> dict[str, Any]:
        data = self._execute(_THEMING_CONFIG)
        return data.get("theming", {}).get("config") or {}

    def apply_theming(
        self,
        *,
        inject_css: str,
        inject_head: str = "",
        inject_body: str = "",
        dark_mode: bool = True,
        theme: str | None = None,
        iconset: str | None = None,
        toc_position: str | None = None,
    ) -> None:
        current = self.get_theming_config()
        variables = {
            "theme": theme or current.get("theme") or "default",
            "iconset": iconset or current.get("iconset") or "mdi",
            "darkMode": dark_mode,
            "tocPosition": toc_position or current.get("tocPosition") or "left",
            "injectCSS": inject_css,
            "injectHead": inject_head,
            "injectBody": inject_body,
        }
        result = self._execute(_SET_THEMING, variables)
        status = result.get("theming", {}).get("setConfig", {}).get("responseResult", {})
        if not status.get("succeeded"):
            raise WikiJsClientError(f"Theming update failed: {status.get('message')}")


def load_esi_theme_css() -> str:
    css_path = Path(__file__).resolve().parent / "assets" / "eve-esi-theme.css"
    if not css_path.is_file():
        raise WikiJsClientError(f"Theme CSS not found: {css_path}")
    return css_path.read_text(encoding="utf-8")


ESI_THEME_HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&family=Source+Code+Pro:wght@400;600&display=swap" rel="stylesheet">
"""
