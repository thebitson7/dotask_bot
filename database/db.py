# database/db.py

from typing import AsyncGenerator
from contextlib import asynccontextmanager
import logging

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.exc import SQLAlchemyError

from core.config import get_settings
from database.models import Base


# ──────────────────────────────────────────────
# ⚙️ Configuration & Logging Setup
# ──────────────────────────────────────────────
logger = logging.getLogger(__name__)
settings = get_settings()

# 🔧 Determine if we log SQL queries (only in dev)
SQL_ECHO = settings.ENV.lower() == "development"


# ──────────────────────────────────────────────
# 🚀 SQLAlchemy Async Engine
# ──────────────────────────────────────────────
engine = create_async_engine(
    settings.DB_URL,
    echo=SQL_ECHO,
    pool_size=10,
    max_overflow=20,
    future=True
)


# ──────────────────────────────────────────────
# 🧪 Async Session Factory
# ──────────────────────────────────────────────
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# ──────────────────────────────────────────────
# 📦 Async Session Context Manager
# ──────────────────────────────────────────────
@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides an async SQLAlchemy session with rollback safety.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except SQLAlchemyError as e:
            await session.rollback()
            logger.exception(f"[DB] ❌ Session rollback due to error: {e}")
            raise
        finally:
            await session.close()


# ──────────────────────────────────────────────
# 🏗️ Initialize All Tables (Run Once)
# ──────────────────────────────────────────────
async def init_db() -> None:
    """
    Initializes the database by creating all tables from models.
    Should be called on startup.
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database initialized successfully.")
    except SQLAlchemyError as e:
        logger.exception("❌ Database initialization failed.")
        raise


# ──────────────────────────────────────────────
# ✨ Exports for External Usage
# ──────────────────────────────────────────────
__all__ = [
    "get_session",
    "init_db",
    "engine",
    "AsyncSessionFactory"
]
