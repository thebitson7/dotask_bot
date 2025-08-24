# database/session.py

from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession
)
from sqlalchemy.exc import SQLAlchemyError

from core.config import get_settings
from database.models import Base

import logging
logger = logging.getLogger(__name__)

# ──────────────────────────────────────
# ⚙️ تنظیمات و ساخت Engine
# ──────────────────────────────────────
settings = get_settings()

engine = create_async_engine(
    settings.DB_URL,
    echo=(settings.ENV == "development"),
    future=True,
    pool_size=5,
    max_overflow=10
)

# ──────────────────────────────────────
# 🧪 ساخت Session Factory
# ──────────────────────────────────────
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# ──────────────────────────────────────
# 📦 گرفتن Session با context manager
# ──────────────────────────────────────
@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except SQLAlchemyError as e:
            await session.rollback()
            logger.exception(f"[DB] ❌ Session rollback: {e}")
            raise
        finally:
            await session.close()


# ──────────────────────────────────────
# 🏗️ ساخت جدول‌های اولیه دیتابیس
# ──────────────────────────────────────
async def init_db() -> None:
    """
    Initializes the database by creating all tables.
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database initialized successfully.")
    except SQLAlchemyError as e:
        logger.exception("❌ Database initialization failed.")
        raise


# ──────────────────────────────────────
# ✨ Exports
# ──────────────────────────────────────
__all__ = [
    "engine",
    "AsyncSessionFactory",
    "get_session",
    "init_db"
]
