"""Create tables on startup (dev-friendly; production may prefer Alembic migrations)."""

import app.db.models as _models  # noqa: F401 — register ORM tables on Base.metadata
import app.sde.models as _sde_models  # noqa: F401 — SDE tables on same Base.metadata
from app.db.models import Base
from app.db.session import get_engine


async def init_schema() -> None:
    engine = get_engine()
    if engine is None:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
