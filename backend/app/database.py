import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.models import Base

logger = logging.getLogger("medmemory.database")

engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=30,
    pool_recycle=settings.database_pool_recycle,
    pool_pre_ping=settings.database_pool_pre_ping,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Initialize database (creates tables in debug; use Alembic in production)."""
    total_attempts = settings.database_init_retries + 1
    for attempt in range(1, total_attempts + 1):
        try:
            async with engine.begin() as conn:
                await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
                if settings.debug:
                    await conn.run_sync(Base.metadata.create_all)
                else:
                    logger.info(
                        "Skipping create_all in non-debug mode; run Alembic migrations."
                    )
            if attempt > 1:
                logger.info("Database initialized after %d attempts", attempt)
            return
        except Exception as exc:
            is_last_attempt = attempt >= total_attempts
            if is_last_attempt:
                logger.exception(
                    "Database initialization failed after %d attempts", attempt
                )
                raise
            delay_seconds = min(
                settings.database_init_retry_delay_seconds * attempt,
                10.0,
            )
            logger.warning(
                "Database initialization attempt %d/%d failed (%s). Retrying in %.1fs.",
                attempt,
                total_attempts,
                exc.__class__.__name__,
                delay_seconds,
            )
            await asyncio.sleep(delay_seconds)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
