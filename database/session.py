# database/session.py
from __future__ import annotations

import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from core.config import get_settings
from database.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()


# ─────────────────────────────────────
# ⚙️ ساخت Engine با تنظیمات سازگار با DB
# ─────────────────────────────────────
def _build_engine() -> AsyncEngine:
    kwargs: dict = {
        "echo": settings.DB_ECHO,
    }

    if settings.db_is_sqlite:
        # برای aiosqlite بهتر است کانکشن‌ها pooled نباشند
        kwargs.update(
            {
                "poolclass": NullPool,
                "connect_args": {"timeout": settings.DB_POOL_TIMEOUT},
            }
        )
    else:
        # برای Postgres/MySQL و … از پارامترهای pool استفاده می‌کنیم
        kwargs.update(
            {
                "pool_size": settings.DB_POOL_SIZE,
                "pool_timeout": settings.DB_POOL_TIMEOUT,
                "max_overflow": 10,
            }
        )

    engine = create_async_engine(settings.DB_URL, **kwargs)

    # PRAGMA های مفید برای SQLite
    if settings.db_is_sqlite:
        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _):  # pragma: no cover
            try:
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON;")
                cur.execute("PRAGMA journal_mode=WAL;")
                cur.execute("PRAGMA synchronous=NORMAL;")
                cur.close()
            except Exception:  # لاگ نزنیم که noisy نشه
                pass

    return engine


engine: AsyncEngine = _build_engine()

# ─────────────────────────────────────
# 🧪 ساخت SessionFactory
# ─────────────────────────────────────
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


# ─────────────────────────────────────
# 📦 گرفتن Session (بدون auto-commit)
# ─────────────────────────────────────
@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager برای سشن معمولی.
    خودت commit/rollback را در CRUD کنترل کن.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            logger.exception("❌ Exception in DB session")
            await session.rollback()
            raise
        finally:
            await session.close()


# ─────────────────────────────────────
# 🔒 سشن تراکنشی (auto-commit/rollback)
# ─────────────────────────────────────
@asynccontextmanager
async def transactional_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager برای تراکنش اتمیک:
    - در پایان موفق → commit
    - در خطا → rollback
    """
    async with AsyncSessionFactory() as session:
        try:
            async with session.begin():
                yield session
        except Exception:
            logger.exception("❌ Exception in transactional session")
            # session.begin() خودش rollback می‌کند؛ اما برای اطمینان:
            try:
                await session.rollback()
            except Exception:
                pass
            raise
        finally:
            await session.close()


# ─────────────────────────────────────
# 🏗️ راه‌اندازی دیتابیس (ایجاد جداول + ping)
# ─────────────────────────────────────
async def init_db() -> None:
    """
    ایجاد جداول در صورت نبود و تست اتصال با یک ping سبک.
    توجه: برای پروژه‌های بزرگ، پیشنهاد Alembic است.
    """
    try:
        # اتصال و ping
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.commit()

        # ساخت جداول
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("✅ Database initialized & reachable.")

    except (OperationalError, SQLAlchemyError) as e:
        logger.critical("❌ Database initialization failed.", exc_info=True)
        raise RuntimeError("Failed to initialize the database.") from e


# ─────────────────────────────────────
# 📴 خاموشی تمیز
# ─────────────────────────────────────
async def shutdown_db() -> None:
    """
    بستن ارتباطات و آزادسازی منابع Engine.
    """
    try:
        await engine.dispose()
        logger.info("🔻 Database engine disposed.")
    except Exception:
        logger.exception("⚠️ Error disposing database engine")
