from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.exc import SQLAlchemyError

from core.config import get_settings
from database.models import Base
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# ─────────────────────────────────────
# ⚙️ ساخت Engine
# ─────────────────────────────────────
engine = create_async_engine(
    settings.DB_URL,
    echo=(settings.ENV == "development"),
    future=True,
)

# ─────────────────────────────────────
# 🧪 ساخت SessionFactory
# ─────────────────────────────────────
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ─────────────────────────────────────
# 📦 گرفتن Session با context manager
# ─────────────────────────────────────
@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception as e:
            logger.exception(f"❌ Exception in DB session: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

# ─────────────────────────────────────
# 🏗️ راه‌اندازی دیتابیس (ایجاد جداول)
# ─────────────────────────────────────
async def init_db() -> None:
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database initialized successfully.")
    except SQLAlchemyError as e:
        logger.critical("❌ Database initialization failed.", exc_info=True)
        raise RuntimeError("Failed to initialize the database.") from e
