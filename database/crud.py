from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from database.models import User, Task
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────
# 👤 واکشی کاربر بر اساس telegram_id
# ───────────────────────────────────────────────
async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int
) -> Optional[User]:
    """
    دریافت کاربر بر اساس آیدی تلگرام.
    """
    try:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalars().first()
    except SQLAlchemyError as e:
        logger.exception(f"[❌ DB] خطا در get_user_by_telegram_id: {e}")
        return None


# ───────────────────────────────────────────────
# ✅ ایجاد یا به‌روزرسانی کاربر
# ───────────────────────────────────────────────
async def create_or_update_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: Optional[str] = None,
    username: Optional[str] = None,
    language: str = "fa"
) -> Optional[User]:
    """
    اگر کاربر قبلاً وجود داشته باشد، اطلاعات او به‌روزرسانی می‌شود.
    در غیر این صورت، یک کاربر جدید ساخته می‌شود.
    """
    try:
        user = await get_user_by_telegram_id(session, telegram_id)

        if user:
            updated = False
            if full_name and user.full_name != full_name:
                user.full_name = full_name
                updated = True
            if username and user.username != username:
                user.username = username
                updated = True
            if language and user.language != language:
                user.language = language
                updated = True

            if updated:
                await session.commit()
                await session.refresh(user)
        else:
            user = User(
                telegram_id=telegram_id,
                full_name=full_name,
                username=username,
                language=language
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        return user

    except SQLAlchemyError as e:
        await session.rollback()
        logger.exception(f"[❌ DB] خطا در create_or_update_user: {e}")
        return None


# ───────────────────────────────────────────────
# 📝 ایجاد تسک جدید برای کاربر
# ───────────────────────────────────────────────
async def create_task(
    session: AsyncSession,
    user_id: int,
    content: str,
    due_date: Optional[datetime] = None
) -> Optional[Task]:
    """
    ایجاد یک تسک جدید برای کاربر با شناسه کاربری و محتوای تسک.
    """
    try:
        task = Task(
            user_id=user_id,
            content=content,
            due_date=due_date,
            is_done=False  # اطمینان از مقدار پیش‌فرض
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task
    except SQLAlchemyError as e:
        await session.rollback()
        logger.exception(f"[❌ DB] خطا در create_task: {e}")
        return None


# ───────────────────────────────────────────────
# 📋 دریافت لیست تسک‌ها بر اساس user_id
# ───────────────────────────────────────────────
async def get_tasks_by_user_id(
    session: AsyncSession,
    user_id: int
) -> List[Task]:
    """
    دریافت همه تسک‌های مرتبط با کاربر به ترتیب جدید به قدیم.
    """
    try:
        result = await session.execute(
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(Task.created_at.desc())
        )
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.exception(f"[❌ DB] خطا در get_tasks_by_user_id: {e}")
        return []
