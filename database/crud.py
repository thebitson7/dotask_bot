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
# 👤 Get user by Telegram ID
# ───────────────────────────────────────────────
async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int
) -> Optional[User]:
    """Retrieve a user based on their Telegram ID."""
    try:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalars().first()
    except SQLAlchemyError as e:
        logger.exception(f"[DB] Failed to fetch user by telegram_id={telegram_id}: {e}")
        return None


# ───────────────────────────────────────────────
# ✅ Create or Update User
# ───────────────────────────────────────────────
async def create_or_update_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: Optional[str] = None,
    username: Optional[str] = None,
    language: str = "fa"
) -> Optional[User]:
    """
    Upserts a user: updates info if exists, else creates a new user.
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
        logger.exception(f"[DB] Failed to create/update user: {e}")
        return None


# ───────────────────────────────────────────────
# 📝 Create New Task
# ───────────────────────────────────────────────
async def create_task(
    session: AsyncSession,
    user_id: int,
    content: str,
    due_date: Optional[datetime] = None
) -> Optional[Task]:
    """Creates a new task for the given user."""
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
        logger.exception(f"[DB] Failed to create task for user_id={user_id}: {e}")
        return None


# ───────────────────────────────────────────────
# 📋 Fetch Tasks for User
# ───────────────────────────────────────────────
async def get_tasks_by_user_id(
    session: AsyncSession,
    user_id: int
) -> List[Task]:
    """Returns all tasks for a given user in descending order of creation."""
    try:
        result = await session.execute(
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(Task.created_at.desc())
        )
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.exception(f"[DB] Failed to fetch tasks for user_id={user_id}: {e}")
        return []
