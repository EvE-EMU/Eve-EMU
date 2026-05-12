"""Load SRP matrix and doctrine JSON from disk (optional override paths)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import settings
from app.schemas_tools import DoctrineBundle, DoctrineDoc, SrpMatrix

log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent


def _srp_file() -> Path:
    raw = (settings.srp_matrix_path or "").strip()
    return Path(raw) if raw else _ROOT / "data" / "srp_matrix.json"


def _doctrine_file() -> Path:
    raw = (settings.doctrines_path or "").strip()
    return Path(raw) if raw else _ROOT / "data" / "doctrines.json"


def load_srp_matrix() -> tuple[SrpMatrix, str | None]:
    """Return matrix and optional error message for UI banners."""
    path = _srp_file()
    try:
        text = path.read_text(encoding="utf-8")
        return SrpMatrix.model_validate_json(text), None
    except FileNotFoundError:
        log.warning("SRP matrix file missing: %s", path)
        return (
            SrpMatrix(
                title="SRP matrix",
                intro=f"File not found: {path}. Create it or set FLEET_TRACKER_SRP_MATRIX_PATH.",
                rows=[],
            ),
            "missing_file",
        )
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        log.warning("SRP matrix invalid (%s): %s", path, exc)
        return (
            SrpMatrix(
                title="SRP matrix (parse error)",
                intro=f"Could not read {path}: {exc}",
                rows=[],
            ),
            "parse_error",
        )


def load_doctrines() -> tuple[DoctrineBundle, str | None]:
    path = _doctrine_file()
    try:
        text = path.read_text(encoding="utf-8")
        return DoctrineBundle.model_validate_json(text), None
    except FileNotFoundError:
        log.warning("Doctrine file missing: %s", path)
        return (
            DoctrineBundle(
                intro=f"File not found: {path}. Create it or set FLEET_TRACKER_DOCTRINES_PATH.",
                doctrines=[],
            ),
            "missing_file",
        )
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        log.warning("Doctrine JSON invalid (%s): %s", path, exc)
        return (
            DoctrineBundle(
                intro=f"Could not read {path}: {exc}",
                doctrines=[],
            ),
            "parse_error",
        )


def get_doctrine_by_slug(slug: str) -> tuple[DoctrineDoc | None, DoctrineBundle]:
    bundle, _ = load_doctrines()
    for d in bundle.doctrines:
        if d.slug == slug:
            return d, bundle
    return None, bundle
