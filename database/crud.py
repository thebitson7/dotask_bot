# database/crud.py
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Task, TaskPriority, User

logger = logging.getLogger(__name__)


# ─────────────────────────────
# 👤 دریافت کاربر با آیدی تلگرام
# ─────────────────────────────
async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int,
) -> Optional[User]:
    try:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalars().first()
    except SQLAlchemyError as e:
        logger.exception("[DB] get_user_by_telegram_id(%s) failed: %s", telegram_id, e)
        return None


# ─────────────────────────────
# ✅ ایجاد یا بروزرسانی کاربر
# ─────────────────────────────
async def create_or_update_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: Optional[str] = None,
    username: Optional[str] = None,
    language: str = "fa",
    *,
    commit: bool = True,
) -> Optional[User]:
    try:
        user = await get_user_by_telegram_id(session, telegram_id)

        if user:
            updated = False
            if full_name and user.full_name != full_name:
                user.full_name = full_name
                updated = True
            if username is not None and user.username != username:
                user.username = username
                updated = True
            if language and user.language != language:
                user.language = language
                updated = True

            if updated and commit:
                await session.commit()
                await session.refresh(user)
                logger.info("[🔄 USER UPDATED] tg=%s", telegram_id)
        else:
            user = User(
                telegram_id=telegram_id,
                full_name=full_name or "بدون‌نام",
                username=username or "",
                language=language or "fa",
            )
            session.add(user)
            if commit:
                await session.commit()
                await session.refresh(user)
            logger.info("[✅ USER CREATED] tg=%s", telegram_id)

        return user

    except SQLAlchemyError as e:
        if commit:
            await session.rollback()
        logger.exception("[DB] create_or_update_user(tg=%s) failed: %s", telegram_id, e)
        return None


# ─────────────────────────────
# 📝 ایجاد تسک جدید
# ─────────────────────────────
async def create_task(
    session: AsyncSession,
    user_id: int,
    content: str,
    due_date: Optional[datetime] = None,
    priority: TaskPriority | str = TaskPriority.MEDIUM,
    *,
    commit: bool = True,
) -> Optional[Task]:
    try:
        content = (content or "").strip()
        if len(content) < 3:
            logger.warning("[⚠️ INVALID CONTENT] user_id=%s -> too short", user_id)
            return None

        if isinstance(priority, str):
            try:
                priority = TaskPriority[priority.upper()]
            except KeyError:
                logger.warning("[⚠️ INVALID PRIORITY] user_id=%s, priority=%r", user_id, priority)
                priority = TaskPriority.MEDIUM

        task = Task(
            user_id=user_id,
            content=content[:255],  # ستون 255
            due_date=due_date,
            priority=priority,
            is_done=False,
        )
        session.add(task)

        if commit:
            await session.commit()
            await session.refresh(task)

        logger.info("[✅ TASK CREATED] user_id=%s task_id=%s", user_id, getattr(task, "id", "?"))
        return task

    except SQLAlchemyError as e:
        if commit:
            await session.rollback()
        logger.exception("[DB] create_task(user_id=%s) failed: %s", user_id, e)
        return None


# ─────────────────────────────
# 📋 دریافت لیست تسک‌ها
# ─────────────────────────────
async def get_tasks_by_user_id(
    session: AsyncSession,
    user_id: int,
    *,
    only_pending: bool = False,
    priority: Optional[TaskPriority] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Task]:
    try:
        query = select(Task).where(Task.user_id == user_id)
        if only_pending:
            query = query.where(Task.is_done.is_(False))
        if priority:
            query = query.where(Task.priority == priority)

        query = query.order_by(Task.created_at.desc())
        if limit is not None:
            query = query.limit(limit).offset(max(0, offset))

        result = await session.execute(query)
        tasks = result.scalars().all()
        logger.debug("[📦 TASKS FETCHED] user_id=%s count=%s", user_id, len(tasks))
        return tasks

    except SQLAlchemyError as e:
        logger.exception("[DB] get_tasks_by_user_id(user_id=%s) failed: %s", user_id, e)
        return []


# ─────────────────────────────
# ✅ علامت‌گذاری تسک به عنوان انجام شده
# ─────────────────────────────
async def mark_task_as_done(
    session: AsyncSession,
    user_id: int,
    task_id: int,
    *,
    commit: bool = True,
) -> Optional[Task]:
    try:
        result = await session.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        task = result.scalars().first()

        if not task:
            logger.info("[ℹ️ TASK NOT FOUND] task_id=%s user_id=%s", task_id, user_id)
            return None

        if task.is_done:
            logger.info("[ℹ️ ALREADY DONE] task_id=%s", task.id)
            return task  # idempotent

        task.is_done = True
        task.done_at = datetime.utcnow()

        if commit:
            await session.commit()
            await session.refresh(task)

        logger.info("[✅ TASK MARKED DONE] task_id=%s user_id=%s", task.id, user_id)
        return task

    except SQLAlchemyError as e:
        if commit:
            await session.rollback()
        logger.exception("[DB] mark_task_as_done(task_id=%s) failed: %s", task_id, e)
        return None


# ─────────────────────────────
# 🗑 حذف تسک
# ─────────────────────────────
async def delete_task_by_id(
    session: AsyncSession,
    user_id: int,
    task_id: int,
    *,
    commit: bool = True,
) -> bool:
    try:
        result = await session.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        task = result.scalars().first()

        if not task:
            logger.info("[ℹ️ TASK NOT FOUND] task_id=%s user_id=%s", task_id, user_id)
            return False

        await session.delete(task)
        if commit:
            await session.commit()

        logger.info("[🗑 TASK DELETED] task_id=%s user_id=%s", task.id, user_id)
        return True

    except SQLAlchemyError as e:
        if commit:
            await session.rollback()
        logger.exception("[DB] delete_task_by_id(task_id=%s) failed: %s", task_id, e)
        return False
