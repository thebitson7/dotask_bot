# database/crud.py

from typing import Optional, List
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Task
import logging

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────
# 👤 دریافت کاربر بر اساس آیدی تلگرام
# ───────────────────────────────────────────────
async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int
) -> Optional[User]:
    try:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalars().first()
    except SQLAlchemyError as e:
        logger.exception(f"[DB] ❌ خطا در دریافت کاربر: telegram_id={telegram_id} -> {e}")
        return None


# ───────────────────────────────────────────────
# ✅ ساخت یا بروزرسانی کاربر
# ───────────────────────────────────────────────
async def create_or_update_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: Optional[str] = None,
    username: Optional[str] = None,
    language: str = "fa"
) -> Optional[User]:
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
        logger.exception(f"[DB] ❌ خطا در ساخت/بروزرسانی کاربر: {e}")
        return None


# ───────────────────────────────────────────────
# 📝 ساخت تسک جدید
# ───────────────────────────────────────────────
async def create_task(
    session: AsyncSession,
    user_id: int,
    content: str,
    due_date: Optional[datetime] = None
) -> Optional[Task]:
    try:
        task = Task(
            user_id=user_id,
            content=content,
            due_date=due_date,
            is_done=False
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task

    except SQLAlchemyError as e:
        await session.rollback()
        logger.exception(f"[DB] ❌ خطا در ساخت تسک: user_id={user_id} -> {e}")
        return None


# ───────────────────────────────────────────────
# 📋 دریافت لیست تسک‌ها بر اساس آی‌دی کاربر
# ───────────────────────────────────────────────
async def get_tasks_by_user_id(
    session: AsyncSession,
    user_id: int
) -> List[Task]:
    try:
        result = await session.execute(
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(Task.created_at.desc())
        )
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.exception(f"[DB] ❌ خطا در دریافت تسک‌ها: user_id={user_id} -> {e}")
        return []


# ───────────────────────────────────────────────
# ✅ علامت‌گذاری تسک به‌عنوان انجام‌شده
# ───────────────────────────────────────────────
async def mark_task_as_done(
    session: AsyncSession,
    user_id: int,
    task_id: int
) -> Optional[Task]:
    """
    علامت‌گذاری تسک به‌عنوان انجام‌شده با استفاده از ID تسک.
    """
    try:
        result = await session.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        task = result.scalars().first()

        if not task:
            logger.warning(f"[⚠️ TASK NOT FOUND] task_id={task_id}, user_id={user_id}")
            return None

        if task.is_done:
            logger.info(f"[ℹ️ TASK ALREADY DONE] task_id={task_id}")
            return None

        task.is_done = True
        task.done_at = datetime.utcnow()

        await session.commit()
        await session.refresh(task)

        logger.info(f"[✅ TASK DONE] task_id={task.id}, user_id={user_id}")
        return task

    except SQLAlchemyError as e:
        await session.rollback()
        logger.exception(f"[DB] ❌ خطا در انجام تسک: task_id={task_id}, user_id={user_id} -> {e}")
        return None
