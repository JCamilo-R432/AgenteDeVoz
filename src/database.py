"""
Async SQLAlchemy 2.0 engine for the order management system.
Supports both PostgreSQL (asyncpg) and SQLite (aiosqlite).
"""

import os
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

# ── Resolve DATABASE_URL ───────────────────────────────────────────────────────

def _get_async_url() -> str:
    """Convert sync DATABASE_URL to async-compatible URL."""
    try:
        from config.settings import settings
        raw_url: str = settings.DATABASE_URL
    except Exception:
        raw_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./orders_dev.db")

    # Already async — return as-is
    if "+asyncpg" in raw_url or "+aiosqlite" in raw_url:
        return raw_url

    # Convert postgresql:// → postgresql+asyncpg://
    if raw_url.startswith("postgresql://") or raw_url.startswith("postgres://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
            "postgres://", "postgresql+asyncpg://", 1
        )

    # Convert sqlite:/// → sqlite+aiosqlite:///
    if raw_url.startswith("sqlite:///"):
        return raw_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

    # Fallback: use SQLite in-memory for safety
    logger.warning(
        f"Could not convert DATABASE_URL '{raw_url}' to async variant. "
        "Falling back to SQLite aiosqlite."
    )
    return "sqlite+aiosqlite:///./orders_dev.db"


# ── Base ───────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ── Engine & Session ───────────────────────────────────────────────────────────

_ASYNC_DATABASE_URL: str = _get_async_url()

_is_sqlite = "sqlite" in _ASYNC_DATABASE_URL

engine = create_async_engine(
    _ASYNC_DATABASE_URL,
    pool_pre_ping=not _is_sqlite,   # SQLite doesn't support pool_pre_ping in the same way
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    # SQLite: connect_args to enable WAL mode for better concurrency
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

logger.info(f"Async database engine created: {_ASYNC_DATABASE_URL.split('@')[-1]}")


# ── Dependency ─────────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession and closes it after use."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
