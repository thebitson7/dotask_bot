# database/crud.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Tuple

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Task, TaskPriority, User

__all__ = [
    # Users
    "create_or_update_user",
    # Tasks create/read
    "create_task",
    "get_tasks_paginated",
    "get_tasks_by_user_id",
    "count_tasks_by_status",
    "get_task_for_user",
    # Mutations
    "set_task_done",
    "mark_task_as_done",      # legacy alias
    "unmark_task_as_done",    # legacy alias
    "delete_task_by_id",
    "update_task_content",
    "snooze_task_by_id",
    # Extras (great for UX flows)
    "set_task_priority",
    "set_task_due_date",
    "search_tasks",
]

# ─────────────────────────────────────────────────────────────
# 🕒 Utilities
# ─────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    """Current UTC (aware)."""
    return datetime.now(timezone.utc)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Coerce datetime to UTC-aware (keeping instant)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # فرض می‌کنیم ورودی از قبل UTC است (pipeline شما UTC ذخیره می‌کند)
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _coerce_positive_int(val: int | str | None, default: int, minimum: int = 1) -> int:
    """Convert to positive int with sane defaults (for page/limit/offset)."""
    try:
        x = int(val) if val is not None else default
    except Exception:
        return default
    return max(minimum, x)


def _priority_from_code(code: str) -> Optional[TaskPriority]:
    """Map 'H'/'M'/'L' -> TaskPriority; otherwise None."""
    mapping = {"H": TaskPriority.HIGH, "M": TaskPriority.MEDIUM, "L": TaskPriority.LOW}
    return mapping.get((code or "").upper())


# ─────────────────────────────────────────────────────────────
# 👤 Users
# ─────────────────────────────────────────────────────────────

async def create_or_update_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    full_name: Optional[str],
    username: Optional[str],
    language: Optional[str],
    commit: bool = False,
) -> Optional[User]:
    """
    Create or update a user by unique telegram_id.
    Returns the ORM User (with id).
    """
    user: Optional[User] = (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()

    now = _utcnow()
    if user is None:
        user = User(
            telegram_id=telegram_id,
            full_name=(full_name or "")[:100] if full_name else None,
            username=(username or "")[:50] if username else None,
            language=(language or "fa")[:10],
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        await session.flush()  # get id
    else:
        changed = False
        if user.full_name != full_name:
            user.full_name = (full_name or "")[:100] if full_name else None
            changed = True
        if user.username != username:
            user.username = (username or "")[:50] if username else None
            changed = True
        if language and user.language != language:
            user.language = language[:10]
            changed = True
        if changed:
            user.updated_at = now
            await session.flush()

    if commit:
        await session.commit()
    return user


# ─────────────────────────────────────────────────────────────
# ➕ Tasks: create
# ─────────────────────────────────────────────────────────────

async def create_task(
    session: AsyncSession,
    *,
    user_id: int,
    content: str,
    due_date: Optional[datetime],
    priority: TaskPriority,
    commit: bool = False,
) -> Optional[Task]:
    """
    Create a new task for a user. `due_date` should be UTC-aware or None.
    """
    now = _utcnow()
    task = Task(
        user_id=user_id,
        content=(content or "")[:255],
        due_date=_ensure_utc(due_date),
        priority=priority,
        is_done=False,
        created_at=now,
        updated_at=now,
        done_at=None,
    )
    session.add(task)
    await session.flush()  # get id

    if commit:
        await session.commit()
    return task


# ─────────────────────────────────────────────────────────────
# 🔎 Tasks: listing (filters + paging)
# ─────────────────────────────────────────────────────────────
# date_filter: 'A' = all, 'T' = today (UTC 00:00..24:00),
#              'W' = this week (UTC, Monday start),
#              'O' = overdue (due < now), 'N' = no due date
# prio_filter: 'A' = all, or 'H'/'M'/'L'

async def get_tasks_paginated(
    session: AsyncSession,
    *,
    user_id: int,
    is_done: Optional[bool],
    prio_filter: str = "A",
    date_filter: str = "A",
    page: int = 1,
    per_page: int = 5,
    now_utc: Optional[datetime] = None,
) -> Tuple[List[Task], int]:
    """
    Returns (rows, total) with filters & pagination.
    Order: open first → closer due_date (NULLs last) → newer created_at.
    """
    if now_utc is None:
        now_utc = _utcnow()

    page = _coerce_positive_int(page, 1)
    per_page = _coerce_positive_int(per_page, 5)

    conds = [Task.user_id == user_id]

    # status
    if is_done is not None:
        conds.append(Task.is_done.is_(True if is_done else False))

    # priority
    prio = _priority_from_code(prio_filter)
    if prio is not None:
        conds.append(Task.priority == prio)

    # date
    if date_filter == "T":  # today (UTC)
        start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        conds.append(and_(Task.due_date.is_not(None), Task.due_date >= start, Task.due_date < end))
    elif date_filter == "W":  # this week (UTC; Monday start)
        weekday = now_utc.weekday()  # Monday=0
        start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=weekday)
        end = start + timedelta(days=7)
        conds.append(and_(Task.due_date.is_not(None), Task.due_date >= start, Task.due_date < end))
    elif date_filter == "O":  # overdue
        conds.append(and_(Task.due_date.is_not(None), Task.due_date < now_utc))
    elif date_filter == "N":  # no due date
        conds.append(Task.due_date.is_(None))
    # 'A' → no date limit

    # total count
    stmt_count = select(func.count()).select_from(Task).where(and_(*conds))
    total: int = int((await session.execute(stmt_count)).scalar_one())

    # paging
    offset = (page - 1) * per_page

    stmt = (
        select(Task)
        .where(and_(*conds))
        .order_by(
            Task.is_done.asc(),               # open first
            Task.due_date.is_(None).asc(),    # tasks with due first
            Task.due_date.asc().nulls_last(), # nearer due first; NULLs last
            Task.created_at.desc(),
        )
        .offset(offset)
        .limit(per_page)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return rows, total


# ─────────────────────────────────────────────────────────────
# 🧾 Quick list for menus / legacy handlers
# ─────────────────────────────────────────────────────────────

async def get_tasks_by_user_id(
    session: AsyncSession,
    *,
    user_id: int,
    is_done: Optional[bool] = None,
    limit: int = 5,
    offset: int = 0,
    only_pending: Optional[bool] = None,
    **_ignored,
) -> List[Task]:
    """
    Return recent tasks for a user, ordered like main listing.
    Compatible with older code via `only_pending`.
    """
    if is_done is None and only_pending is not None:
        is_done = False if only_pending else True

    limit = _coerce_positive_int(limit, 5)
    offset = max(0, int(offset or 0))

    conds = [Task.user_id == user_id]
    if is_done is not None:
        conds.append(Task.is_done.is_(True if is_done else False))

    stmt = (
        select(Task)
        .where(and_(*conds))
        .order_by(
            Task.is_done.asc(),
            Task.due_date.is_(None).asc(),
            Task.due_date.asc().nulls_last(),
            Task.created_at.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return (await session.execute(stmt)).scalars().all()


# ─────────────────────────────────────────────────────────────
# 🔢 Counts (open/done)
# ─────────────────────────────────────────────────────────────

async def count_tasks_by_status(
    session: AsyncSession,
    *,
    user_id: int,
) -> Tuple[int, int]:
    """Return (open_count, done_count)."""
    total_open = (
        await session.execute(
            select(func.count()).select_from(Task).where(Task.user_id == user_id, Task.is_done.is_(False))
        )
    ).scalar_one()

    total_done = (
        await session.execute(
            select(func.count()).select_from(Task).where(Task.user_id == user_id, Task.is_done.is_(True))
        )
    ).scalar_one()

    return int(total_open), int(total_done)


# ─────────────────────────────────────────────────────────────
# 🔍 Get single task safely
# ─────────────────────────────────────────────────────────────

async def get_task_for_user(
    session: AsyncSession,
    *,
    user_id: int,
    task_id: int,
) -> Optional[Task]:
    """Fetch one task by id for a given user (or None)."""
    stmt = select(Task).where(Task.id == task_id, Task.user_id == user_id)
    return (await session.execute(stmt)).scalars().first()


# ─────────────────────────────────────────────────────────────
# ✅ Done / Undo
# ─────────────────────────────────────────────────────────────

async def set_task_done(
    session: AsyncSession,
    *,
    user_id: int,
    task_id: int,
    done: bool = True,
    commit: bool = False,
) -> bool:
    now = _utcnow()
    stmt = (
        update(Task)
        .where(Task.id == task_id, Task.user_id == user_id)
        .values(
            is_done=done,
            done_at=now if done else None,
            updated_at=now,
        )
    )
    result = await session.execute(stmt)
    if commit:
        await session.commit()
    return (result.rowcount or 0) > 0


# Aliases (سازگاری با کد قدیمی)
async def mark_task_as_done(
    session: AsyncSession,
    *,
    user_id: int,
    task_id: int,
    commit: bool = False,
) -> bool:
    return await set_task_done(
        session, user_id=user_id, task_id=task_id, done=True, commit=commit
    )


async def unmark_task_as_done(
    session: AsyncSession,
    *,
    user_id: int,
    task_id: int,
    commit: bool = False,
) -> bool:
    return await set_task_done(
        session, user_id=user_id, task_id=task_id, done=False, commit=commit
    )


# ─────────────────────────────────────────────────────────────
# 🗑 Delete
# ─────────────────────────────────────────────────────────────

async def delete_task_by_id(
    session: AsyncSession,
    *,
    user_id: int,
    task_id: int,
    commit: bool = False,
) -> bool:
    stmt = delete(Task).where(Task.id == task_id, Task.user_id == user_id)
    result = await session.execute(stmt)
    if commit:
        await session.commit()
    return (result.rowcount or 0) > 0


# ─────────────────────────────────────────────────────────────
# ✏️ Update content
# ─────────────────────────────────────────────────────────────

async def update_task_content(
    session: AsyncSession,
    *,
    user_id: int,
    task_id: int,
    new_content: str,
    commit: bool = False,
) -> bool:
    now = _utcnow()
    stmt = (
        update(Task)
        .where(Task.id == task_id, Task.user_id == user_id)
        .values(content=(new_content or "")[:255], updated_at=now)
    )
    result = await session.execute(stmt)
    if commit:
        await session.commit()
    return (result.rowcount or 0) > 0


# ─────────────────────────────────────────────────────────────
# 🔁 Snooze
# ─────────────────────────────────────────────────────────────

async def snooze_task_by_id(
    session: AsyncSession,
    *,
    user_id: int,
    task_id: int,
    delta_minutes: int,
    commit: bool = False,
) -> bool:
    now = _utcnow()
    task: Optional[Task] = (
        await session.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not task:
        return False

    base = task.due_date or now
    minutes = _coerce_positive_int(delta_minutes, 15)
    new_due = base + timedelta(minutes=minutes)
    stmt = (
        update(Task)
        .where(Task.id == task_id, Task.user_id == user_id)
        .values(due_date=_ensure_utc(new_due), updated_at=now)
    )
    result = await session.execute(stmt)
    if commit:
        await session.commit()
    return (result.rowcount or 0) > 0


# ─────────────────────────────────────────────────────────────
# 🎚 Priority & 🗓 Due date mutations
# ─────────────────────────────────────────────────────────────

async def set_task_priority(
    session: AsyncSession,
    *,
    user_id: int,
    task_id: int,
    priority: TaskPriority,
    commit: bool = False,
) -> bool:
    now = _utcnow()
    stmt = (
        update(Task)
        .where(Task.id == task_id, Task.user_id == user_id)
        .values(priority=priority, updated_at=now)
    )
    result = await session.execute(stmt)
    if commit:
        await session.commit()
    return (result.rowcount or 0) > 0


async def set_task_due_date(
    session: AsyncSession,
    *,
    user_id: int,
    task_id: int,
    due_date: Optional[datetime],
    commit: bool = False,
) -> bool:
    now = _utcnow()
    stmt = (
        update(Task)
        .where(Task.id == task_id, Task.user_id == user_id)
        .values(due_date=_ensure_utc(due_date), updated_at=now)
    )
    result = await session.execute(stmt)
    if commit:
        await session.commit()
    return (result.rowcount or 0) > 0


# ─────────────────────────────────────────────────────────────
# 🔎 Search (content LIKE, + optional filters) with paging
# ─────────────────────────────────────────────────────────────

async def search_tasks(
    session: AsyncSession,
    *,
    user_id: int,
    query: str,
    is_done: Optional[bool] = None,
    prio_in: Optional[Iterable[TaskPriority]] = None,
    limit: int = 10,
    offset: int = 0,
) -> Tuple[List[Task], int]:
    """
    Simple LIKE-based search on content with optional filters.
    Returns (rows, total). Ordering matches main listing.
    """
    q = (query or "").strip()
    if not q:
        return [], 0

    limit = _coerce_positive_int(limit, 10)
    offset = max(0, int(offset or 0))

    conds = [Task.user_id == user_id, Task.content.ilike(f"%{q}%")]

    if is_done is not None:
        conds.append(Task.is_done.is_(True if is_done else False))

    if prio_in:
        conds.append(Task.priority.in_(list(prio_in)))

    # total
    stmt_count = select(func.count()).select_from(Task).where(and_(*conds))
    total = int((await session.execute(stmt_count)).scalar_one())

    # rows
    stmt = (
        select(Task)
        .where(and_(*conds))
        .order_by(
            Task.is_done.asc(),
            Task.due_date.is_(None).asc(),
            Task.due_date.asc().nulls_last(),
            Task.created_at.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return rows, total
