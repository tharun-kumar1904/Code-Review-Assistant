"""
Database configuration — async SQLAlchemy engine, session factory, and pgvector setup.
Gracefully handles missing asyncpg driver (for local dev without PostgreSQL).
"""

import logging

logger = logging.getLogger(__name__)

try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.orm import DeclarativeBase
    from sqlalchemy import text
    from config import get_settings

    settings = get_settings()

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.APP_ENV == "development",
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )

    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    class Base(DeclarativeBase):
        """Declarative base for all ORM models."""
        pass

    async def init_db():
        """Create all tables and enable pgvector extension."""
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)

    async def get_db() -> AsyncSession:
        """Dependency — yields a database session."""
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    DB_AVAILABLE = True

except Exception as e:
    logger.warning(f"Database not available: {e}. Running in RL-only mode.")
    DB_AVAILABLE = False

    class Base:
        pass

    async def init_db():
        logger.info("Skipping DB init — asyncpg not installed")

    async def get_db():
        raise RuntimeError("Database not available. Install asyncpg for DB features.")
