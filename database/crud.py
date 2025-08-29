# database/crud.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, delete, func, select, update
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
    # Mutations
    "set_task_done",
    "mark_task_as_done",      # legacy alias
    "unmark_task_as_done",    # legacy alias
    "delete_task_by_id",
    "update_task_content",
    "snooze_task_by_id",
]

# ─────────────────────────────────────────────────────────────
# 🕒 Utilities
# ─────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    """Current UTC (aware)."""
    return datetime.now(timezone.utc)


def _coerce_positive_int(val: int | str | None, default: int, minimum: int = 1) -> int:
    """به مقدار صحیح مثبت تبدیل می‌کند (برای page/limit/offset)."""
    try:
        x = int(val) if val is not None else default
    except Exception:
        return default
    return max(minimum, x)


def _priority_from_code(code: str) -> Optional[TaskPriority]:
    """Map 'H'/'M'/'L' -> TaskPriority; otherwise None."""
    mapping = {"H": TaskPriority.HIGH, "M": TaskPriority.MEDIUM, "L": TaskPriority.LOW}
    return mapping.get(code)


# ─────────────────────────────────────────────────────────────
# 👤 کاربر: ساخت/به‌روزرسانی
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
    کاربر را با کلید یکتای telegram_id می‌سازد یا اگر موجود باشد به‌روز می‌کند.
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
        # برای دریافت id
        await session.flush()
    else:
        changed = False
        # فقط اگر مقدار جدید متفاوت است
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
# ➕ تسک: ساخت
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
    یک تسک جدید برای کاربر می‌سازد. `due_date` باید UTC-aware باشد یا None.
    """
    now = _utcnow()
    task = Task(
        user_id=user_id,
        content=(content or "")[:255],
        due_date=due_date,
        priority=priority,
        is_done=False,
        created_at=now,
        updated_at=now,
        done_at=None,
    )
    session.add(task)
    await session.flush()  # id

    if commit:
        await session.commit()
    return task


# ─────────────────────────────────────────────────────────────
# 🔎 فهرست تسک‌ها با فیلتر و صفحه‌بندی
# ─────────────────────────────────────────────────────────────
# date_filter: 'A' = همه، 'T' = امروز (UTC، 00:00..24:00)،
#              'W' = این هفته (UTC، شروع دوشنبه)،
#              'O' = گذشته (overdue)، 'N' = بدون تاریخ
# prio_filter: 'A' = همه، یا 'H'/'M'/'L'

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
    برمی‌گرداند (rows, total) با فیلترهای وضعیت/اولویت/تاریخ و صفحه‌بندی.
    ترتیب: بازها → due_date نزدیک‌تر (Null آخر) → created_at جدیدتر.
    """
    if now_utc is None:
        now_utc = _utcnow()

    page = _coerce_positive_int(page, 1)
    per_page = _coerce_positive_int(per_page, 5)

    conds = [Task.user_id == user_id]

    # وضعیت
    if is_done is not None:
        conds.append(Task.is_done.is_(True if is_done else False))

    # اولویت
    prio = _priority_from_code(prio_filter)
    if prio is not None:
        conds.append(Task.priority == prio)

    # تاریخ
    if date_filter == "T":  # امروز (UTC)
        start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        conds.append(and_(Task.due_date.is_not(None), Task.due_date >= start, Task.due_date < end))
    elif date_filter == "W":  # این هفته (UTC؛ دوشنبه شروع)
        weekday = now_utc.weekday()  # Monday=0
        start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=weekday)
        end = start + timedelta(days=7)
        conds.append(and_(Task.due_date.is_not(None), Task.due_date >= start, Task.due_date < end))
    elif date_filter == "O":  # گذشته/Overdue
        conds.append(and_(Task.due_date.is_not(None), Task.due_date < now_utc))
    elif date_filter == "N":  # بدون تاریخ
        conds.append(Task.due_date.is_(None))
    # 'A' → بدون محدودیت تاریخ

    # شمارش کل
    stmt_count = select(func.count()).select_from(Task).where(and_(*conds))
    total: int = int((await session.execute(stmt_count)).scalar_one())

    # صفحه‌بندی
    offset = (page - 1) * per_page

    # ترتیب
    stmt = (
        select(Task)
        .where(and_(*conds))
        .order_by(
            Task.is_done.asc(),               # بازها جلوتر
            Task.due_date.is_(None).asc(),    # dueدارها جلوتر
            Task.due_date.asc().nulls_last(), # نزدیک‌ترها جلوتر؛ Null آخر
            Task.created_at.desc(),
        )
        .offset(offset)
        .limit(per_page)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return rows, total


# ─────────────────────────────────────────────────────────────
# 🧾 گرفتن چند تسک اخیر کاربر (برای منو/نمایش سریع)
# ─────────────────────────────────────────────────────────────
# سازگار با نسخه‌های قدیمی: only_pending و … نادیده‌گیری امن پارامترهای اضافی

async def get_tasks_by_user_id(
    session: AsyncSession,
    *,
    user_id: int,
    is_done: Optional[bool] = None,
    limit: int = 5,
    offset: int = 0,
    only_pending: Optional[bool] = None,
    **_ignored,  # پارامترهای غیرمنتظره از هندلرهای قدیمی
) -> List[Task]:
    """
    چند تسک اخیر کاربر را برمی‌گرداند.
    - is_done=None  → همه
    - is_done=False → فقط بازها
    - is_done=True  → فقط انجام‌شده‌ها

    Backward-compatible:
      - اگر is_done مشخص نیست و only_pending داده شده:
          only_pending=True  -> is_done=False
          only_pending=False -> is_done=True
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
# 🔢 شمارش سریع تسک‌ها برای منو
# ─────────────────────────────────────────────────────────────

async def count_tasks_by_status(
    session: AsyncSession,
    *,
    user_id: int,
) -> Tuple[int, int]:
    """(open_count, done_count)"""
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
# ✅ انجام/برگرداندن انجام‌نشده
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
# 🗑 حذف
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
# ✏️ ویرایش محتوا
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
# 🔁 اسنوز/تعویق
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
    try:
        minutes = _coerce_positive_int(delta_minutes, 15)
    except Exception:
        minutes = 15

    new_due = base + timedelta(minutes=minutes)
    stmt = (
        update(Task)
        .where(Task.id == task_id, Task.user_id == user_id)
        .values(due_date=new_due, updated_at=now)
    )
    result = await session.execute(stmt)
    if commit:
        await session.commit()
    return (result.rowcount or 0) > 0
