from typing import Optional, List
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Task, TaskPriority
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────
# 👤 دریافت کاربر با آیدی تلگرام
# ─────────────────────────────
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
        logger.exception(f"[❌ DB ERROR] get_user_by_telegram_id(telegram_id={telegram_id}) -> {e}")
        return None


# ─────────────────────────────
# ✅ ایجاد یا بروزرسانی کاربر
# ─────────────────────────────
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
                logger.info(f"[🔄 USER UPDATED] telegram_id={telegram_id}")

        else:
            user = User(
                telegram_id=telegram_id,
                full_name=full_name or "بدون‌نام",
                username=username or "",
                language=language or "fa"
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            logger.info(f"[✅ USER CREATED] telegram_id={telegram_id}")

        return user

    except SQLAlchemyError as e:
        await session.rollback()
        logger.exception(f"[❌ DB ERROR] create_or_update_user(telegram_id={telegram_id}) -> {e}")
        return None


# ─────────────────────────────
# 📝 ایجاد تسک جدید
# ─────────────────────────────
async def create_task(
    session: AsyncSession,
    user_id: int,
    content: str,
    due_date: Optional[datetime] = None,
    priority: TaskPriority | str = TaskPriority.MEDIUM
) -> Optional[Task]:
    try:
        content = content.strip()
        if len(content) < 2:
            logger.warning(f"[⚠️ INVALID CONTENT] user_id={user_id} -> Content too short.")
            return None

        if isinstance(priority, str):
            try:
                priority = TaskPriority(priority.lower())
            except ValueError:
                logger.warning(f"[⚠️ INVALID PRIORITY] user_id={user_id}, priority={priority}")
                priority = TaskPriority.MEDIUM

        task = Task(
            user_id=user_id,
            content=content,
            due_date=due_date,
            priority=priority,
            is_done=False
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        logger.info(f"[✅ TASK CREATED] user_id={user_id}, task_id={task.id}")
        return task

    except SQLAlchemyError as e:
        await session.rollback()
        logger.exception(f"[❌ DB ERROR] create_task(user_id={user_id}) -> {e}")
        return None


# ─────────────────────────────
# 📋 دریافت لیست تسک‌ها
# ─────────────────────────────
async def get_tasks_by_user_id(
    session: AsyncSession,
    user_id: int,
    only_pending: bool = False,
    priority: Optional[TaskPriority] = None
) -> List[Task]:
    try:
        query = select(Task).where(Task.user_id == user_id)

        if only_pending:
            query = query.where(Task.is_done.is_(False))
        if priority:
            query = query.where(Task.priority == priority)

        query = query.order_by(Task.created_at.desc())
        result = await session.execute(query)
        tasks = result.scalars().all()

        logger.debug(f"[📦 TASKS FETCHED] user_id={user_id}, count={len(tasks)}")
        return tasks

    except SQLAlchemyError as e:
        logger.exception(f"[❌ DB ERROR] get_tasks_by_user_id(user_id={user_id}) -> {e}")
        return []


# ─────────────────────────────
# ✅ علامت‌گذاری تسک به عنوان انجام شده
# ─────────────────────────────
async def mark_task_as_done(
    session: AsyncSession,
    user_id: int,
    task_id: int
) -> Optional[Task]:
    try:
        result = await session.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        task = result.scalars().first()

        if not task:
            logger.warning(f"[⚠️ TASK NOT FOUND] task_id={task_id}, user_id={user_id}")
            return None

        if task.is_done:
            logger.info(f"[ℹ️ ALREADY DONE] task_id={task.id}")
            return None

        task.is_done = True
        task.done_at = datetime.utcnow()

        await session.commit()
        await session.refresh(task)
        logger.info(f"[✅ TASK MARKED DONE] task_id={task.id}, user_id={user_id}")
        return task

    except SQLAlchemyError as e:
        await session.rollback()
        logger.exception(f"[❌ DB ERROR] mark_task_as_done(task_id={task_id}) -> {e}")
        return None


# ─────────────────────────────
# 🗑 حذف تسک
# ─────────────────────────────
async def delete_task_by_id(
    session: AsyncSession,
    user_id: int,
    task_id: int
) -> bool:
    try:
        result = await session.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        task = result.scalars().first()

        if not task:
            logger.warning(f"[⚠️ TASK NOT FOUND] task_id={task_id}, user_id={user_id}")
            return False

        await session.delete(task)
        await session.commit()
        logger.info(f"[🗑 TASK DELETED] task_id={task.id}, user_id={user_id}")
        return True

    except SQLAlchemyError as e:
        await session.rollback()
        logger.exception(f"[❌ DB ERROR] delete_task_by_id(task_id={task_id}) -> {e}")
        return False
