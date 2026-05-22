from sqlalchemy import text

from app.db.models import Base
from app.db.session import get_engine


async def _migrate(conn) -> None:
    await conn.execute(
        text(
            "ALTER TABLE market_types "
            "ADD COLUMN IF NOT EXISTS market_group_id INTEGER"
        )
    )
    for col in ("amarr_sell", "amarr_buy"):
        await conn.execute(
            text(f"ALTER TABLE type_appraisals ADD COLUMN IF NOT EXISTS {col} DOUBLE PRECISION")
        )


async def init_schema() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate(conn)
