# database/session.py
from __future__ import annotations

import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager
import contextlib

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

__all__ = [
    "engine",
    "AsyncSessionFactory",
    "get_session",
    "transactional_session",
    "init_db",
    "shutdown_db",
]

# ─────────────────────────────────────
# ⚙️ ساخت Engine با تنظیمات سازگار با DB
# ─────────────────────────────────────
def _build_engine() -> AsyncEngine:
    """
    یک AsyncEngine سازگار با دو جهان SQLite/غیر-SQLite می‌سازد:
    - SQLite (aiosqlite): NullPool + PRAGMAهای مناسب + timeout
    - Postgres/MySQL: pool با pre_ping و بازیافت اتصال
    """
    # پارامترهای عمومی
    kwargs: dict = {
        "echo": settings.DB_ECHO,
        # برای استخرهای واقعی مفیده؛ برای SQLite بی‌معنیه ولی بی‌ضرره
        "pool_pre_ping": not settings.db_is_sqlite,
        # برخی درایورها با recycle مناسب، اتصال‌های Idle را تازه می‌کنند
        "pool_recycle": getattr(settings, "DB_POOL_RECYCLE", 1800),  # 30m
    }

    if settings.db_is_sqlite:
        # aiosqlite: استخر لازم نیست؛ NullPool پایدارتره
        kwargs.update(
            {
                "poolclass": NullPool,
                # timeout به ثانیه (همون چیزی که در config ست کردی)
                "connect_args": {
                    "timeout": settings.DB_POOL_TIMEOUT,
                    # isolation_level=None → autocommit mode مناسب WAL
                    "isolation_level": None,
                },
            }
        )
    else:
        # استخر واقعی برای Postgres/MySQL و …
        kwargs.update(
            {
                "pool_size": settings.DB_POOL_SIZE,
                "pool_timeout": settings.DB_POOL_TIMEOUT,
                "max_overflow": getattr(settings, "DB_MAX_OVERFLOW", 10),
            }
        )

    engine = create_async_engine(settings.DB_URL, **kwargs)

    # PRAGMA های مفید برای SQLite (فقط بار اول هر اتصال)
    if settings.db_is_sqlite:
        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _):  # pragma: no cover
            try:
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON;")
                cur.execute("PRAGMA journal_mode=WAL;")
                cur.execute("PRAGMA synchronous=NORMAL;")
                cur.execute("PRAGMA temp_store=MEMORY;")
                cur.execute("PRAGMA cache_size=-20000;")  # ~20MB
                cur.close()
            except Exception:
                # عمداً کم‌نویز
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
    expire_on_commit=False,  # شیءها بعد از commit معتبر می‌مانند (برای بات عالیه)
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
            try:
                await session.rollback()
            except Exception:
                pass
            raise
        finally:
            # AsyncSession __aexit__ خودش close می‌کند؛ اما برای شفافیت:
            try:
                await session.close()
            except Exception:
                pass

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
            # session.begin() خودش rollback می‌کند؛ فقط اطمینان:
            with contextlib.suppress(Exception):
                await session.rollback()
            raise
        finally:
            with contextlib.suppress(Exception):
                await session.close()

# ─────────────────────────────────────
# 🏗️ راه‌اندازی دیتابیس (ایجاد جداول + ping)
# ─────────────────────────────────────
async def init_db() -> None:
    """
    ایجاد جداول در صورت نبود و تست اتصال با یک ping سبک.
    توجه: در محیط‌های Production حتماً Alembic توصیه می‌شود.
    """
    try:
        # اتصال و ping
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.commit()

        # ساخت جداول به‌صورت ایمن (checkfirst=True)
        async with engine.begin() as conn:
            def _create_all(sync_conn):
                Base.metadata.create_all(sync_conn, checkfirst=True)
            await conn.run_sync(_create_all)

        logger.info("✅ Database initialized & reachable.")

    except (OperationalError, SQLAlchemyError):
        logger.critical("❌ Database initialization failed.", exc_info=True)
        raise RuntimeError("Failed to initialize the database.")

# ─────────────────────────────────────
# 📴 خاموشی تمیز
# ─────────────────────────────────────
async def shutdown_db() -> None:
    """بستن ارتباطات و آزادسازی منابع Engine."""
    try:
        await engine.dispose()
        logger.info("🔻 Database engine disposed.")
    except Exception:
        logger.exception("⚠️ Error disposing database engine")
