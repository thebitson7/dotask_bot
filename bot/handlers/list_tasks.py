# bot/handlers/list_tasks.py
from __future__ import annotations

import contextlib
import logging
from datetime import datetime, timezone
from math import ceil
from typing import Dict, List, Tuple, Optional

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from zoneinfo import ZoneInfo

from sqlalchemy import select

from core.config import get_settings
from database.session import transactional_session
from database.crud import (
    get_tasks_paginated,
    set_task_done,
    delete_task_by_id,
    update_task_content,
    snooze_task_by_id,
)
from database.models import Task, TaskPriority, User
from bot.keyboards.listing import (
    build_list_header_keyboard,
    build_task_actions_keyboard,
)
from fsm.states import EditTask

router = Router()
logger = logging.getLogger("bot.handlers.list_tasks")
settings = get_settings()
LOCAL_TZ = ZoneInfo(settings.TZ)

# ─────────────────────────────────────────
# ⚙️ تنظیمات و ثابت‌ها
# ─────────────────────────────────────────
PER_PAGE = 5
DEFAULT_STATUS = "o"  # o=open, d=done
DEFAULT_PRIO = "A"    # A/H/M/L
DEFAULT_DATE = "A"    # A/T/W/O/N

_LIST_TRIGGERS = {
    "📋 لیست تسک‌ها",
    "📋 نمایش تسک‌ها",
    "📋 تسک‌ها",
    "🗂 لیست کارها",
    "📋 لیست وظایف",
}

# در حافظه: پیام‌های آخرین سری کارت‌ها برای هر چت
_LAST_BATCH: Dict[int, List[int]] = {}

# ─────────────────────────────────────────
# 🧩 ابزارهای کمکی
# ─────────────────────────────────────────
def _parse_kv(s: str) -> Tuple[str, Dict[str, str]]:
    if ";" in s:
        head, rest = s.split(";", 1)
    else:
        head, rest = s, ""
    kv: Dict[str, str] = {}
    if rest:
        for chunk in rest.split(";"):
            if not chunk or "=" not in chunk:
                continue
            k, v = chunk.split("=", 1)
            kv[k] = v
    return head, kv

def _safe_int(v: str | int, default: int = 1) -> int:
    try:
        x = int(v)
        return x if x > 0 else default
    except Exception:
        return default

def _fmt_due_local(due_utc: Optional[datetime | str]) -> str:
    if not due_utc:
        return "بدون تاریخ"
    dt: datetime
    if isinstance(due_utc, str):
        try:
            dt = datetime.fromisoformat(due_utc)
        except Exception:
            return "بدون تاریخ"
    else:
        dt = due_utc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        local = dt.astimezone(LOCAL_TZ)
        now = datetime.now(LOCAL_TZ)
        if local.date() == now.date():
            return f"امروز {local.strftime('%H:%M')}"
        delta = local - now
        secs = int(delta.total_seconds())
        if secs < 0:
            hours = abs(secs) // 3600
            if hours >= 24:
                days = hours // 24
                return f"گذشته ({days} روز)"
            return f"گذشته ({hours} ساعت)"
        hours = secs // 3600
        if hours >= 24:
            days = hours // 24
            return f"تا {days} روز"
        return f"تا {hours} ساعت"
    except Exception:
        return "بدون تاریخ"

def _prio_icon(prio: TaskPriority) -> str:
    name = prio.name if isinstance(prio, TaskPriority) else str(prio)
    return {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(name, "⚪️")

def _page_counter(page: int, per_page: int, total: int) -> Tuple[int, int, str]:
    total_pages = max(1, ceil(max(0, total) / max(1, per_page)))
    page = max(1, min(page, total_pages))
    return page, total_pages, f"صفحه {page}/{total_pages}"

def _ctx_from_kv(kv: Dict[str, str]) -> Tuple[str, int, str, str]:
    s = kv.get("s", DEFAULT_STATUS)
    p = _safe_int(kv.get("p", "1"), 1)
    f = kv.get("f", DEFAULT_PRIO)
    d = kv.get("d", DEFAULT_DATE)
    return s, p, f, d

async def _get_user_db_id(session, telegram_id: int) -> Optional[int]:
    row = await session.execute(select(User.id).where(User.telegram_id == telegram_id))
    return row.scalar_one_or_none()

# ─────────────────────────────────────────
# 🖼 رندر کارت‌ها
# ─────────────────────────────────────────
def _render_header_text(*, total: int, status: str, prio_filter: str, date_filter: str, page: int) -> str:
    title = "📋 تسک‌های باز" if status == "o" else "✅ تسک‌های انجام‌شده"
    prio_map = {"A": "همه", "H": "بالا", "M": "متوسط", "L": "پایین"}
    date_map = {"A": "همه", "T": "امروز", "W": "این هفته", "O": "گذشته", "N": "بدون تاریخ"}
    return (
        f"{title} (کل: {total})\n"
        f"🔎 فیلترها → اولویت: {prio_map.get(prio_filter,'همه')} | تاریخ: {date_map.get(date_filter,'همه')}"
    )

def _render_task_card_text(idx: int, t: Task) -> str:
    pr = _prio_icon(t.priority)
    due = _fmt_due_local(t.due_date)
    status = "✅ انجام‌شده" if t.is_done else "⏳ در انتظار"
    lines = [
        "— — — — — — — — — — —",
        f"{idx}. {pr} <b>{t.content}</b>",
        f"وضعیت: {status}",
        f"⏰ موعد: {due}",
    ]
    return "\n".join(lines)

async def _delete_last_batch(chat_id: int, *, bot, keep_header_id: Optional[int]) -> None:
    ids = _LAST_BATCH.pop(chat_id, [])
    if not ids:
        return
    for mid in ids:
        if keep_header_id and mid == keep_header_id:
            continue
        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id, mid)

async def _store_batch(chat_id: int, message_ids: List[int]) -> None:
    _LAST_BATCH[chat_id] = message_ids

# ─────────────────────────────────────────
# 📥 دریافت داده‌ها (با تبدیل tg_id→user_id)
# ─────────────────────────────────────────
async def _fetch_page(
    *,
    tg_id: int,
    status: str,
    page: int,
    prio_filter: str,
    date_filter: str,
    now_utc: datetime,
) -> Tuple[List[Task], int, int]:
    is_done: Optional[bool]
    if status == "o":
        is_done = False
    elif status == "d":
        is_done = True
    else:
        is_done = None

    async with transactional_session() as session:
        user_db_id = await _get_user_db_id(session, telegram_id=tg_id)
        if user_db_id is None:
            return [], 0, max(1, page or 1)

        tasks, total = await get_tasks_paginated(
            session,
            user_id=user_db_id,
            is_done=is_done,
            prio_filter=prio_filter,
            date_filter=date_filter,
            page=page,
            per_page=PER_PAGE,
            now_utc=now_utc,
        )

        if not tasks and page > 1:
            _, total_pages, _ = _page_counter(page, PER_PAGE, total)
            fixed_page = max(1, total_pages)
            if fixed_page != page:
                tasks, total = await get_tasks_paginated(
                    session,
                    user_id=user_db_id,
                    is_done=is_done,
                    prio_filter=prio_filter,
                    date_filter=date_filter,
                    page=fixed_page,
                    per_page=PER_PAGE,
                    now_utc=now_utc,
                )
                return tasks, total, fixed_page

    return tasks, total, page

# ─────────────────────────────────────────
# 🎯 نمایش هدر + کارت‌ها
# ─────────────────────────────────────────
async def _show_cards(
    *,
    source: Message | CallbackQuery,
    status: str,
    page: int,
    prio_filter: str,
    date_filter: str,
    edit_header: bool = False,
) -> None:
    chat_id = source.chat.id if isinstance(source, Message) else source.message.chat.id
    now_utc = datetime.now(timezone.utc)

    tasks, total, page = await _fetch_page(
        tg_id=source.from_user.id,  # ← تلگرام آی‌دی؛ داخل تابع به user_db_id تبدیل می‌شود
        status=status,
        page=page,
        prio_filter=prio_filter,
        date_filter=date_filter,
        now_utc=now_utc,
    )

    header_text = _render_header_text(
        total=total, status=status, prio_filter=prio_filter, date_filter=date_filter, page=page
    )
    header_kb = build_list_header_keyboard(
        status=status, page=page, per_page=PER_PAGE, total=total, prio_filter=prio_filter, date_filter=date_filter
    )

    # 1) هدر
    if isinstance(source, Message):
        header_msg = await source.answer(header_text, reply_markup=header_kb)
    else:
        try:
            if edit_header:
                header_msg = await source.message.edit_text(header_text, reply_markup=header_kb)
            else:
                header_msg = await source.message.answer(header_text, reply_markup=header_kb)
        except Exception as e:
            logger.debug("edit header failed -> %s ; fallback to new", e)
            header_msg = await source.message.answer(header_text, reply_markup=header_kb)
        with contextlib.suppress(Exception):
            await source.answer()

    # 2) پاکسازی کارت‌های قبلی
    await _delete_last_batch(chat_id, bot=header_msg.bot, keep_header_id=header_msg.message_id)

    # 3) کارت‌های جدید
    sent_ids: List[int] = [header_msg.message_id]
    if not tasks:
        await _store_batch(chat_id, sent_ids)
        return

    idx_start = (page - 1) * PER_PAGE
    for i, t in enumerate(tasks, start=idx_start + 1):
        text = _render_task_card_text(i, t)
        kb = build_task_actions_keyboard(
            task_id=t.id, status=status, page=page, prio_filter=prio_filter, date_filter=date_filter
        )
        msg = await header_msg.answer(text, reply_markup=kb)
        sent_ids.append(msg.message_id)

    await _store_batch(chat_id, sent_ids)

# ─────────────────────────────────────────
# 🚪 ورود به لیست
# ─────────────────────────────────────────
@router.message(F.text.in_(_LIST_TRIGGERS))
async def entry_list(message: Message) -> None:
    await _show_cards(
        source=message,
        status=DEFAULT_STATUS,
        page=1,
        prio_filter=DEFAULT_PRIO,
        date_filter=DEFAULT_DATE,
    )

# ─────────────────────────────────────────
# ♻️ ناوبری/فیلتر لیست (روی هدر)
# ─────────────────────────────────────────
@router.callback_query(F.data.startswith("tlist"))
async def on_list_nav(cb: CallbackQuery) -> None:
    _, kv = _parse_kv(cb.data)
    s, p, f, d = _ctx_from_kv(kv)
    await _show_cards(source=cb, status=s, page=p, prio_filter=f, date_filter=d, edit_header=True)

@router.callback_query(F.data.in_({"noop", "noop:listing"}))
async def noop_listing(cb: CallbackQuery) -> None:
    with contextlib.suppress(Exception):
        await cb.answer(" ")

# ─────────────────────────────────────────
# 🧨 اکشن‌ها: done / undo / del / edit / snz
# ─────────────────────────────────────────
@router.callback_query(F.data.startswith("tact:done:"))
async def act_done(cb: CallbackQuery) -> None:
    head, kv = _parse_kv(cb.data)
    try:
        _, _, id_str = head.split(":", 2); tid = int(id_str)
    except Exception:
        await cb.answer("❗ داده نامعتبر"); return
    s, p, f, d = _ctx_from_kv(kv)

    async with transactional_session() as session:
        user_db_id = await _get_user_db_id(session, telegram_id=cb.from_user.id)
        if user_db_id is None:
            await cb.answer("❗ کاربر نامعتبر"); return
        ok = await set_task_done(session, user_id=user_db_id, task_id=tid, done=True, commit=False)

    await cb.answer("✅ انجام شد" if ok else "❗ خطا")
    await _show_cards(source=cb, status=s, page=p, prio_filter=f, date_filter=d, edit_header=True)

@router.callback_query(F.data.startswith("tact:undo:"))
async def act_undo(cb: CallbackQuery) -> None:
    head, kv = _parse_kv(cb.data)
    try:
        _, _, id_str = head.split(":", 2); tid = int(id_str)
    except Exception:
        await cb.answer("❗ داده نامعتبر"); return
    s, p, f, d = _ctx_from_kv(kv)

    async with transactional_session() as session:
        user_db_id = await _get_user_db_id(session, telegram_id=cb.from_user.id)
        if user_db_id is None:
            await cb.answer("❗ کاربر نامعتبر"); return
        ok = await set_task_done(session, user_id=user_db_id, task_id=tid, done=False, commit=False)

    await cb.answer("↩️ بازگردانده شد" if ok else "❗ خطا")
    await _show_cards(source=cb, status=s, page=p, prio_filter=f, date_filter=d, edit_header=True)

@router.callback_query(F.data.startswith("tact:del:"))
async def act_delete(cb: CallbackQuery) -> None:
    head, kv = _parse_kv(cb.data)
    try:
        _, _, id_str = head.split(":", 2); tid = int(id_str)
    except Exception:
        await cb.answer("❗ داده نامعتبر"); return
    s, p, f, d = _ctx_from_kv(kv)

    async with transactional_session() as session:
        user_db_id = await _get_user_db_id(session, telegram_id=cb.from_user.id)
        if user_db_id is None:
            await cb.answer("❗ کاربر نامعتبر"); return
        ok = await delete_task_by_id(session, user_id=user_db_id, task_id=tid, commit=False)

    await cb.answer("🗑 حذف شد" if ok else "❗ خطا")
    await _show_cards(source=cb, status=s, page=p, prio_filter=f, date_filter=d, edit_header=True)

# ✏️ ویرایش محتوا
@router.callback_query(F.data.startswith("tact:edit:"))
async def act_edit_start(cb: CallbackQuery, state: FSMContext) -> None:
    head, kv = _parse_kv(cb.data)
    try:
        _, _, id_str = head.split(":", 2); tid = int(id_str)
    except Exception:
        await cb.answer("❗ داده نامعتبر"); return
    s, p, f, d = _ctx_from_kv(kv)
    await state.set_state(EditTask.waiting_for_new_content)
    await state.update_data(task_id=tid, s=s, p=p, f=f, d=d)
    await cb.answer()
    await cb.message.answer("✏️ متن جدید تسک را بفرستید (برای انصراف: /cancel)")

@router.message(EditTask.waiting_for_new_content, F.text)
async def act_edit_save(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        tid = int(data["task_id"])
    except Exception:
        await state.clear()
        await message.answer("❗ جلسه ویرایش معتبر نبود. دوباره تلاش کنید.")
        return
    s = data.get("s", DEFAULT_STATUS)
    p = int(data.get("p", 1))
    f = data.get("f", DEFAULT_PRIO)
    d = data.get("d", DEFAULT_DATE)

    new_text = (message.text or "").strip()
    if len(new_text) < 3:
        await message.answer("❗ متن کوتاه است. حداقل ۳ کاراکتر."); return

    async with transactional_session() as session:
        user_db_id = await _get_user_db_id(session, telegram_id=message.from_user.id)
        if user_db_id is None:
            await message.answer("❗ کاربر نامعتبر."); await state.clear(); return
        ok = await update_task_content(
            session, user_id=user_db_id, task_id=tid, new_content=new_text, commit=False
        )

    await state.clear()
    await message.answer("✅ ویرایش شد." if ok else "❗ خطا در ویرایش.")
    await _show_cards(source=message, status=s, page=p, prio_filter=f, date_filter=d)

# 🔁 اسنوز (انتخاب مدت)
def _snooze_keyboard(tid: int, *, s: str, p: int, f: str, d: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    options = [("15m", 15), ("1h", 60), ("1d", 60*24), ("3d", 60*24*3), ("1w", 60*24*7)]
    for label, mins in options:
        b.button(text=label, callback_data=f"tsnz:{tid}:{mins};s={s};p={p};f={f};d={d}")
    b.button(text="❌ انصراف", callback_data=f"tlist;s={s};p={p};f={f};d={d}")
    b.adjust(3, 2)
    return b.as_markup()

@router.callback_query(F.data.startswith("tact:snz:"))
async def act_snooze_open(cb: CallbackQuery) -> None:
    head, kv = _parse_kv(cb.data)
    try:
        _, _, id_str = head.split(":", 2); tid = int(id_str)
    except Exception:
        await cb.answer("❗ داده نامعتبر"); return
    s, p, f, d = _ctx_from_kv(kv)
    await cb.message.edit_reply_markup(reply_markup=_snooze_keyboard(tid, s=s, p=p, f=f, d=d))
    await cb.answer("⏰ مدت تعویق را انتخاب کنید…")

@router.callback_query(F.data.startswith("tsnz:"))
async def act_snooze_apply(cb: CallbackQuery) -> None:
    head, kv = _parse_kv(cb.data)
    try:
        _, id_str, mins_str = head.split(":", 2)
        tid = int(id_str); mins = _safe_int(mins_str, 15)
    except Exception:
        await cb.answer("❗ داده نامعتبر"); return

    s, p, f, d = _ctx_from_kv(kv)
    async with transactional_session() as session:
        user_db_id = await _get_user_db_id(session, telegram_id=cb.from_user.id)
        if user_db_id is None:
            await cb.answer("❗ کاربر نامعتبر"); return
        ok = await snooze_task_by_id(
            session, user_id=user_db_id, task_id=tid, delta_minutes=mins, commit=False
        )
    await cb.answer("🔁 اسنوز شد" if ok else "❗ خطا")
    await _show_cards(source=cb, status=s, page=p, prio_filter=f, date_filter=d, edit_header=True)
