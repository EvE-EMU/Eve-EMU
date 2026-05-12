"""Async SQLAlchemy engine and session factory (optional when ``CORE_DATABASE_URL`` unset)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine, _session_factory
    if not settings.database_url:
        return None
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Yield a session; no-op path should not be used by routes that require DB."""
    factory = _session_factory
    if factory is None:
        raise RuntimeError("Database not configured (set CORE_DATABASE_URL)")
    async with factory() as session:
        yield session
