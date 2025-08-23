from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager
from core.config import get_settings
from database.models import Base
import logging

# --- تنظیمات و لاگ ---
logger = logging.getLogger(__name__)
settings = get_settings()

# --- تعریف Engine با Connection Pool ---
engine = create_async_engine(
    settings.DB_URL,
    echo=settings.ENV == "development",  # فقط در dev لاگ بزن
    pool_size=10,
    max_overflow=20,
    future=True
)

# --- تعریف Session Factory ---
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# --- Context Manager برای گرفتن سشن (مثبت برای FastAPI) ---
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

# --- ایجاد جداول ---
async def init_db() -> None:
    """
    اجرای اولیه و ایجاد جداول دیتابیس
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database initialized successfully.")
    except SQLAlchemyError as e:
        logger.exception("❌ Database initialization failed.")
        raise

# برای کنترل اکسپورت از این ماژول
__all__ = ["get_session", "init_db", "engine", "AsyncSessionFactory"]
