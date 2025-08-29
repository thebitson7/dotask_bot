# bot/handlers/list_tasks.py
from __future__ import annotations

import contextlib
import logging
from datetime import datetime, timezone
from math import ceil
from typing import Dict, List, Tuple, Optional

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from zoneinfo import ZoneInfo

from core.config import get_settings
from database.session import transactional_session
from database.crud import (
    create_or_update_user,   # ⬅️ برای نگاشت TG→DB
    get_tasks_paginated,
    set_task_done,
    delete_task_by_id,
    update_task_content,
    snooze_task_by_id,
)
from database.models import Task, TaskPriority
from bot.keyboards.listing import build_listing_keyboard
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

# ورودی‌های شروع (چند متن رایج)
_LIST_TRIGGERS = {
    "📋 لیست تسک‌ها",
    "📋 نمایش تسک‌ها",
    "📋 تسک‌ها",
    "🗂 لیست کارها",
    "📋 لیست وظایف",  # برای سازگاری با منو/متون دیگر
}

# ─────────────────────────────────────────
# 🧩 ابزارهای کمکی
# ─────────────────────────────────────────
def _parse_kv(s: str) -> Tuple[str, Dict[str, str]]:
    """
    ورودی مثل:
      "tlist;s=o;p=1;f=A;d=A"
      "tact:done:123;s=o;p=2;f=H;d=T"
    خروجی: (head, {s:'o', p:'1', f:'A', d:'A'})
    """
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

    with contextlib.suppress(Exception):
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
        else:
            hours = secs // 3600
            if hours >= 24:
                days = hours // 24
                return f"تا {days} روز"
            return f"تا {hours} ساعت"

    return "بدون تاریخ"


def _prio_icon(prio: TaskPriority) -> str:
    name = prio.name if isinstance(prio, TaskPriority) else str(prio)
    return {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(name, "⚪️")


def _page_counter(page: int, per_page: int, total: int) -> Tuple[int, int, str]:
    total_pages = max(1, ceil(max(0, total) / max(1, per_page)))
    page = max(1, min(page, total_pages))
    return page, total_pages, f"صفحه {page}/{total_pages}"


async def _db_user_id_from_tg(user) -> Optional[int]:
    """
    Telegram user → DB user.id
    - اگر کاربر نبود، می‌سازیم/به‌روزرسانی می‌کنیم (idempotent)
    """
    try:
        async with transactional_session() as session:
            u = await create_or_update_user(
                session=session,
                telegram_id=user.id,
                full_name=user.full_name,
                username=user.username,
                language=(user.language_code or settings.DEFAULT_LANG),
                commit=False,
            )
            return u.id if u else None
    except Exception as e:
        logger.exception("💥 USER MAP FAILED tg=%s -> %s", getattr(user, "id", "?"), e)
        return None


def _render_list_text(
    *,
    tasks: List[Task],
    page: int,
    per_page: int,
    total: int,
    status: str,
    prio_filter: str,
    date_filter: str,
) -> str:
    page, total_pages, page_label = _page_counter(page, per_page, total)
    title = "📋 تسک‌های باز" if status == "o" else "✅ تسک‌های انجام‌شده"
    prio_map = {"A": "همه", "H": "بالا", "M": "متوسط", "L": "پایین"}
    date_map = {"A": "همه", "T": "امروز", "W": "این هفته", "O": "گذشته", "N": "بدون تاریخ"}
    meta = f"🔎 فیلترها → اولویت: {prio_map.get(prio_filter,'همه')} | تاریخ: {date_map.get(date_filter,'همه')}"

    if not tasks:
        return f"{title}\n\nهیچ آیتمی اینجا نیست.\n\n{meta}\n{page_label}"

    lines = [f"{title} (کل: {total})", ""]
    idx_start = (page - 1) * per_page

    for i, t in enumerate(tasks, start=idx_start + 1):
        pr = _prio_icon(t.priority)
        due = _fmt_due_local(t.due_date)
        done = "✅" if t.is_done else "⏳"
        lines.append(f"{i}. {pr} {t.content}  •  {done}  •  {due}")

    lines += ["", meta, page_label]
    return "\n".join(lines)


async def _fetch_page(
    *,
    db_user_id: int,
    status: str,
    page: int,
    prio_filter: str,
    date_filter: str,
    now_utc: datetime,
) -> Tuple[List[Task], int, int]:
    """
    داده‌های صفحه خواسته‌شده را می‌گیرد؛ اگر page خارج از بازه بود، آن را به آخرین صفحه اصلاح می‌کند و دوباره می‌گیرد.
    خروجی: (tasks, total, final_page)
    """
    is_done: Optional[bool]
    if status == "o":
        is_done = False
    elif status == "d":
        is_done = True
    else:
        is_done = None

    async with transactional_session() as session:
        tasks, total = await get_tasks_paginated(
            session,
            user_id=db_user_id,            # ⬅️ DB user.id (نه Telegram ID)
            is_done=is_done,
            prio_filter=prio_filter,
            date_filter=date_filter,
            page=page,
            per_page=PER_PAGE,
            now_utc=now_utc,
        )

        # اگر صفحه خالی و page > 1 بود، به آخرین صفحه برویم
        if not tasks and page > 1:
            _, total_pages, _ = _page_counter(page, PER_PAGE, total)
            fixed_page = max(1, total_pages)
            if fixed_page != page:
                tasks, total = await get_tasks_paginated(
                    session,
                    user_id=db_user_id,
                    is_done=is_done,
                    prio_filter=prio_filter,
                    date_filter=date_filter,
                    page=fixed_page,
                    per_page=PER_PAGE,
                    now_utc=now_utc,
                )
                return tasks, total, fixed_page

    return tasks, total, page


async def _show_list(
    *,
    source: Message | CallbackQuery,
    status: str = DEFAULT_STATUS,
    page: int = 1,
    prio_filter: str = DEFAULT_PRIO,
    date_filter: str = DEFAULT_DATE,
    edit: bool = False,
    db_user_id: Optional[int] = None,   # ⬅️ برای پاس‌دادن مستقیم (اگر قبلاً گرفتیم)
) -> None:
    # نگاشت TG→DB (اگر پاس نشده بود)
    if db_user_id is None:
        db_user_id = await _db_user_id_from_tg(source.from_user)
    if not db_user_id:
        # اگر کاربر در DB ثبت نشد، پیام راهنما بده
        txt = "❗ حساب شما شناسایی نشد. لطفاً /start را بزنید."
        if isinstance(source, Message):
            await source.answer(txt)
        else:
            with contextlib.suppress(Exception):
                await source.message.answer(txt)
                await source.answer()
        return

    now_utc = datetime.now(timezone.utc)

    # دریافت داده‌ها با اصلاح احتمالی صفحه
    tasks, total, page = await _fetch_page(
        db_user_id=db_user_id,
        status=status,
        page=page,
        prio_filter=prio_filter,
        date_filter=date_filter,
        now_utc=now_utc,
    )

    # متن و کیبورد
    text = _render_list_text(
        tasks=tasks,
        page=page,
        per_page=PER_PAGE,
        total=total,
        status=status,
        prio_filter=prio_filter,
        date_filter=date_filter,
    )
    kb = build_listing_keyboard(
        task_ids=[t.id for t in tasks],
        status=status,
        page=page,
        per_page=PER_PAGE,
        total=total,
        prio_filter=prio_filter,
        date_filter=date_filter,
    )

    # ارسال/ویرایش پیام
    if isinstance(source, Message):
        await source.answer(text, reply_markup=kb)
    else:
        try:
            if edit:
                await source.message.edit_text(text, reply_markup=kb)
            else:
                await source.message.answer(text, reply_markup=kb)
        except Exception as e:
            logger.debug("edit_text failed -> %s ; falling back to answer()", e)
            with contextlib.suppress(Exception):
                await source.message.answer(text, reply_markup=kb)
        with contextlib.suppress(Exception):
            await source.answer()  # بستن لودینگ


# ─────────────────────────────────────────
# 🚪 ورود به لیست
# ─────────────────────────────────────────
@router.message(F.text.in_(_LIST_TRIGGERS))
async def entry_list(message: Message) -> None:
    db_uid = await _db_user_id_from_tg(message.from_user)
    await _show_list(
        source=message,
        status=DEFAULT_STATUS,
        page=1,
        prio_filter=DEFAULT_PRIO,
        date_filter=DEFAULT_DATE,
        db_user_id=db_uid,  # ⬅️ پاس می‌دهیم تا دوباره resolve نشود
    )


# ─────────────────────────────────────────
# ♻️ ناوبری/فیلتر لیست
# ─────────────────────────────────────────
@router.callback_query(F.data.startswith("tlist"))
async def on_list_nav(cb: CallbackQuery) -> None:
    _, kv = _parse_kv(cb.data)
    s = kv.get("s", DEFAULT_STATUS)
    p = _safe_int(kv.get("p", "1"), 1)
    f = kv.get("f", DEFAULT_PRIO)
    d = kv.get("d", DEFAULT_DATE)
    db_uid = await _db_user_id_from_tg(cb.from_user)
    await _show_list(source=cb, status=s, page=p, prio_filter=f, date_filter=d, edit=True, db_user_id=db_uid)


# دکمهٔ وسط صفحه «noop» — هم نسخه‌ی قدیمی هم جدید
@router.callback_query(F.data.in_({"noop", "noop:listing"}))
async def noop_listing(cb: CallbackQuery) -> None:
    with contextlib.suppress(Exception):
        await cb.answer(" ")


# ─────────────────────────────────────────
# 🧨 اکشن‌ها: done / undo / del / edit / snz
# ─────────────────────────────────────────
def _ctx_from_kv(kv: Dict[str, str]) -> Tuple[str, int, str, str]:
    s = kv.get("s", DEFAULT_STATUS)
    p = _safe_int(kv.get("p", "1"), 1)
    f = kv.get("f", DEFAULT_PRIO)
    d = kv.get("d", DEFAULT_DATE)
    return s, p, f, d


@router.callback_query(F.data.startswith("tact:done:"))
async def act_done(cb: CallbackQuery) -> None:
    head, kv = _parse_kv(cb.data)
    try:
        _, _, id_str = head.split(":", 2)
        tid = int(id_str)
    except Exception:
        await cb.answer("❗ داده نامعتبر")
        return
    s, p, f, d = _ctx_from_kv(kv)

    db_uid = await _db_user_id_from_tg(cb.from_user)
    if not db_uid:
        await cb.answer("❗ حساب شما شناسایی نشد.", show_alert=True)
        return

    async with transactional_session() as session:
        ok = await set_task_done(session, user_id=db_uid, task_id=tid, done=True, commit=False)
    await cb.answer("✅ انجام شد" if ok else "❗ خطا")
    await _show_list(source=cb, status=s, page=p, prio_filter=f, date_filter=d, edit=True, db_user_id=db_uid)


@router.callback_query(F.data.startswith("tact:undo:"))
async def act_undo(cb: CallbackQuery) -> None:
    head, kv = _parse_kv(cb.data)
    try:
        _, _, id_str = head.split(":", 2)
        tid = int(id_str)
    except Exception:
        await cb.answer("❗ داده نامعتبر")
        return
    s, p, f, d = _ctx_from_kv(kv)

    db_uid = await _db_user_id_from_tg(cb.from_user)
    if not db_uid:
        await cb.answer("❗ حساب شما شناسایی نشد.", show_alert=True)
        return

    async with transactional_session() as session:
        ok = await set_task_done(session, user_id=db_uid, task_id=tid, done=False, commit=False)
    await cb.answer("↩️ به حالت باز برگشت" if ok else "❗ خطا")
    await _show_list(source=cb, status=s, page=p, prio_filter=f, date_filter=d, edit=True, db_user_id=db_uid)


@router.callback_query(F.data.startswith("tact:del:"))
async def act_delete(cb: CallbackQuery) -> None:
    head, kv = _parse_kv(cb.data)
    try:
        _, _, id_str = head.split(":", 2)
        tid = int(id_str)
    except Exception:
        await cb.answer("❗ داده نامعتبر")
        return
    s, p, f, d = _ctx_from_kv(kv)

    db_uid = await _db_user_id_from_tg(cb.from_user)
    if not db_uid:
        await cb.answer("❗ حساب شما شناسایی نشد.", show_alert=True)
        return

    async with transactional_session() as session:
        ok = await delete_task_by_id(session, user_id=db_uid, task_id=tid, commit=False)
    await cb.answer("🗑 حذف شد" if ok else "❗ خطا")

    await _show_list(source=cb, status=s, page=p, prio_filter=f, date_filter=d, edit=True, db_user_id=db_uid)


# ✏️ ویرایش (نسخه‌ی ساده: فقط محتوا را با پیام بعدی می‌گیرد)
@router.callback_query(F.data.startswith("tact:edit:"))
async def act_edit_start(cb: CallbackQuery, state: FSMContext) -> None:
    head, kv = _parse_kv(cb.data)
    try:
        _, _, id_str = head.split(":", 2)
        tid = int(id_str)
    except Exception:
        await cb.answer("❗ داده نامعتبر")
        return
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
        await message.answer("❗ متن کوتاه است. حداقل ۳ کاراکتر.")
        return

    db_uid = await _db_user_id_from_tg(message.from_user)
    if not db_uid:
        await message.answer("❗ حساب شما شناسایی نشد. /start را بزنید.")
        await state.clear()
        return

    async with transactional_session() as session:
        ok = await update_task_content(
            session,
            user_id=db_uid,
            task_id=tid,
            new_content=new_text,
            commit=False,
        )

    await state.clear()
    await message.answer("✅ ویرایش شد." if ok else "❗ خطا در ویرایش.")
    await _show_list(source=message, status=s, page=p, prio_filter=f, date_filter=d, db_user_id=db_uid)


# 🔁 اسنوز: مرحله ۱ → انتخاب مدت
def _snooze_keyboard(tid: int, *, s: str, p: int, f: str, d: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    options = [
        ("15m", 15),
        ("1h", 60),
        ("1d", 60 * 24),
        ("3d", 60 * 24 * 3),
        ("1w", 60 * 24 * 7),
    ]
    for label, mins in options:
        b.button(text=label, callback_data=f"tsnz:{tid}:{mins};s={s};p={p};f={f};d={d}")
    b.button(text="❌ انصراف", callback_data=f"tlist;s={s};p={p};f={f};d={d}")
    b.adjust(3, 2)
    return b.as_markup()


@router.callback_query(F.data.startswith("tact:snz:"))
async def act_snooze_open(cb: CallbackQuery) -> None:
    head, kv = _parse_kv(cb.data)
    try:
        _, _, id_str = head.split(":", 2)
        tid = int(id_str)
    except Exception:
        await cb.answer("❗ داده نامعتبر")
        return
    s, p, f, d = _ctx_from_kv(kv)
    await cb.message.edit_reply_markup(reply_markup=_snooze_keyboard(tid, s=s, p=p, f=f, d=d))
    await cb.answer("⏰ مدت تعویق را انتخاب کنید…")


@router.callback_query(F.data.startswith("tsnz:"))
async def act_snooze_apply(cb: CallbackQuery) -> None:
    head, kv = _parse_kv(cb.data)
    try:
        _, id_str, mins_str = head.split(":", 2)
        tid = int(id_str)
        mins = _safe_int(mins_str, 15)
    except Exception:
        await cb.answer("❗ داده نامعتبر")
        return

    s, p, f, d = _ctx_from_kv(kv)

    db_uid = await _db_user_id_from_tg(cb.from_user)
    if not db_uid:
        await cb.answer("❗ حساب شما شناسایی نشد.", show_alert=True)
        return

    async with transactional_session() as session:
        ok = await snooze_task_by_id(
            session, user_id=db_uid, task_id=tid, delta_minutes=mins, commit=False
        )
    await cb.answer("🔁 اسنوز شد" if ok else "❗ خطا")
    await _show_list(source=cb, status=s, page=p, prio_filter=f, date_filter=d, edit=True, db_user_id=db_uid)
