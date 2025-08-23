# database/session.py

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager

from core.config import get_settings
from database.models import Base

settings = get_settings()

# 🎯 Engine ساخت
engine = create_async_engine(
    settings.DB_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    future=True
)

# 🎯 Session factory تعریف
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

# 🎯 گرفتن سشن برای استفاده در هرجای پروژه
@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except SQLAlchemyError as e:
            await session.rollback()
            raise e
        finally:
            await session.close()

# 🎯 ساخت جداول
async def init_db() -> None:
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database initialized.")
    except SQLAlchemyError as e:
        print("❌ Database initialization failed:", str(e))
