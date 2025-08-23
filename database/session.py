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

# ────────────── تنظیمات و لاگینگ ──────────────
settings = get_settings()
logger = logging.getLogger(__name__)

# ────────────── Engine ساخت ──────────────
engine = create_async_engine(
    settings.DB_URL,
    echo=(settings.ENV == "development"),
    pool_size=10,
    max_overflow=20,
    future=True
)

# ────────────── Session Factory ──────────────
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# ────────────── گرفتن Session با Context Manager ──────────────
@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except SQLAlchemyError as e:
            await session.rollback()
            logger.exception(f"[❌ DB] Session rollback due to error: {e}")
            raise
        finally:
            await session.close()

# ────────────── مقداردهی اولیه دیتابیس ──────────────
async def init_db() -> None:
    """
    Initializes the database and creates all tables.
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database initialized successfully.")
    except SQLAlchemyError as e:
        logger.exception("❌ Database initialization failed.")
        raise

# ────────────── کنترل خروجی این فایل ──────────────
__all__ = ["get_session", "init_db", "engine", "AsyncSessionFactory"]
