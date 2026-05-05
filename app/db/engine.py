"""
SQLAlchemy Async Engine and Session Management.

Provides:
- AsyncEngine: PostgreSQL async engine using asyncpg
- AsyncSession: async session factory
- get_db(): dependency injection for FastAPI routes
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from sqlalchemy.ext.asyncio import async_sessionmaker
from typing import AsyncGenerator

from app.core.config import settings


# Base class for ORM models
class Base(DeclarativeBase):
    pass


# Create async engine
# pool_pre_ping=True for connection health check
# echo=False set to True for SQL debugging
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
)


# Async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database session.

    Usage:
        @router.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database tables.
    Call this at application startup.
    """
    async with engine.begin() as conn:
        # Use sync connection to run metadata create_all
        # This creates all tables defined in Base.metadata
        await conn.run_sync(Base.metadata.create_all)


async def init_db_if_not_exists() -> None:
    """
    Initialize database tables if they don't exist.
    This is a safer version that checks for existing tables first.
    """
    from sqlalchemy import text

    async with engine.begin() as conn:
        try:
            # Check if users table exists
            await conn.execute(text("SELECT 1 FROM users LIMIT 1"))
            # If we get here, table exists, no need to create
            return
        except Exception:
            # Table doesn't exist, create all tables
            await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close database connections.
    Call this at application shutdown.
    """
    await engine.dispose()
