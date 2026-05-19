"""One-shot: create FastAPI / SQLAlchemy tables (same as app lifespan init_schema)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Running as ``python scripts/this.py`` puts ``scripts/`` on sys.path[0], not the app root.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.db.init_schema import init_schema


def main() -> None:
    asyncio.run(init_schema())


if __name__ == "__main__":
    main()
