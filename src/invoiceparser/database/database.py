"""
Database connection and session management.
"""
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

# Import Base after models are defined
from .models import Base

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(database_url: str, echo: bool = False, pool_size: int = 5, max_overflow: int = 10) -> None:
    """
    Initialize database connection.

    Args:
        database_url: Database connection URL (postgresql+asyncpg://...)
        echo: Enable SQLAlchemy query logging
        pool_size: Connection pool size
        max_overflow: Maximum overflow connections
    """
    global _engine, _session_factory

    if _engine is not None:
        logger.warning("Database already initialized")
        return

    _engine = create_async_engine(
        database_url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,  # Verify connections before using
    )

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    logger.info("Database initialized")


async def close_db() -> None:
    """Close database connection."""
    global _engine, _session_factory

    if _engine is None:
        return

    await _engine.dispose()
    _engine = None
    _session_factory = None

    logger.info("Database connection closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session.

    Usage:
        async with get_session() as session:
            # Use session
            pass
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_engine() -> AsyncEngine:
    """Get database engine (for migrations, etc.)."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine
