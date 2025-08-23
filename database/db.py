# database/db.py

from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.exc import SQLAlchemyError

from core.config import get_settings
from database.models import Base

import logging


# ─────────────────────────────
# 🔧 Configuration & Logging
# ─────────────────────────────
logger = logging.getLogger(__name__)
settings = get_settings()


# ─────────────────────────────
# ⚙️ Engine Setup
# ─────────────────────────────
engine = create_async_engine(
    settings.DB_URL,
    echo=(settings.ENV == "development"),
    pool_size=10,
    max_overflow=20,
    future=True
)


# ─────────────────────────────
# 🧪 Session Factory
# ─────────────────────────────
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# ─────────────────────────────
# 🎯 Async Context Session
# ─────────────────────────────
@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides an async SQLAlchemy session with safe rollback & cleanup.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except SQLAlchemyError as e:
            await session.rollback()
            logger.exception(f"[❌ DB] Rollback due to error: {e}")
            raise
        finally:
            await session.close()


# ─────────────────────────────
# 🏗️ Database Initialization
# ─────────────────────────────
async def init_db() -> None:
    """
    Initializes database & creates all tables from models.
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database initialized successfully.")
    except SQLAlchemyError as e:
        logger.exception("❌ Failed to initialize the database.")
        raise


# ─────────────────────────────
# 📦 Exports
# ─────────────────────────────
__all__ = ["get_session", "init_db", "engine", "AsyncSessionFactory"]
