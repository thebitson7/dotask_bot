# bot/handlers/add_task.py
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from zoneinfo import ZoneInfo

from bot.keyboards.main_menu import main_menu_keyboard
from bot.keyboards.priority import (
    priority_keyboard,
    parse_priority_from_callback,
    priority_label,
)
from core.config import get_settings
from database.crud import create_or_update_user, create_task
from database.models import TaskPriority
from database.session import transactional_session
from fsm.states import AddTask

router = Router()
logger = logging.getLogger(__name__)
settings = get_settings()

# ───────────────────────────────
# 🔧 Helpers
# ───────────────────────────────
CONTENT_MAX_LEN = 255
LOCAL_TZ = ZoneInfo(settings.TZ)


def _normalize_content(text: str) -> str:
    """Trim/condense whitespace and enforce DB max length."""
    text = (text or "").strip()
    normalized = " ".join(text.split())
    if len(normalized) > CONTENT_MAX_LEN:
        logger.info("✂️ Trimming content from %d to %d chars", len(normalized), CONTENT_MAX_LEN)
        normalized = normalized[:CONTENT_MAX_LEN]
    return normalized


def _now_local() -> datetime:
    return datetime.now(tz=LOCAL_TZ)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(timezone.utc)


def _parse_custom_date(s: str, *, default_time: tuple[int, int] = (9, 0)) -> Optional[datetime]:
    """
    Try multiple common formats; if date-only, attach default time (09:00 local).
    Supported:
      - YYYY-MM-DD
      - YYYY-MM-DD HH:MM
      - DD.MM.YYYY
      - DD.MM.YYYY HH:MM
      - YYYY/MM/DD
    """
    s = (s or "").strip()
    formats: Iterable[tuple[str, bool]] = (
        ("%Y-%m-%d %H:%M", True),
        ("%Y-%m-%d", False),
        ("%d.%m.%Y %H:%M", True),
        ("%d.%m.%Y", False),
        ("%Y/%m/%d", False),
    )
    for fmt, has_time in formats:
        try:
            dt = datetime.strptime(s, fmt)
            if not has_time:
                dt = dt.replace(hour=default_time[0], minute=default_time[1])
            return dt.replace(tzinfo=LOCAL_TZ)
        except ValueError:
            continue
    return None


def _due_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📅 امروز", "due:today"),
        ("🕒 فردا", "due:tomorrow"),
        ("🔥 فوری (۲ ساعت)", "due:urgent"),
        ("🗓 آخر هفته", "due:week"),
        ("❌ بدون تاریخ", "due:none"),
        ("✍️ دلخواه", "due:manual"),
    ]
    for text, data in buttons:
        builder.button(text=text, callback_data=data)
    builder.adjust(2)
    return builder.as_markup()


async def _safe_answer(source: Message | CallbackQuery, text: str, **kwargs) -> None:
    try:
        if isinstance(source, Message):
            await source.answer(text, **kwargs)
        else:
            await source.message.answer(text, **kwargs)
    except Exception as e:  # pragma: no cover
        logger.warning("⚠️ Failed to send message to user=%s -> %s", source.from_user.id, e)


def _lang_of(user) -> str:
    """Detect user language or fallback to default."""
    return (getattr(user, "language_code", None) or settings.DEFAULT_LANG or "fa").lower()


# ───────────────────────────────
# 🎯 مرحله 1: شروع افزودن تسک
# ───────────────────────────────
@router.message(F.text == "➕ افزودن تسک")
async def start_add_task(message: Message, state: FSMContext) -> None:
    logger.info("➕ ADD TASK start by user %s", message.from_user.id)

    # تضمین ایجاد/به‌روز کاربر پیش از ورود به FSM
    async with transactional_session() as session:
        user = await create_or_update_user(
            session=session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
            language=_lang_of(message.from_user),
            commit=False,  # transactional_session خودش commit می‌کند
        )
        if not user:
            await message.answer("❗ خطا در ایجاد حساب کاربری. لطفاً /start را بزنید.")
            return

    await message.answer(
        "📝 لطفاً محتوای تسک را وارد کنید (مثلاً: خرید نان):",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(AddTask.waiting_for_content)


# ───────────────────────────────
# ✍️ مرحله 2: دریافت محتوای تسک
# ───────────────────────────────
@router.message(AddTask.waiting_for_content, F.text)
async def receive_content(message: Message, state: FSMContext) -> None:
    content = _normalize_content(message.text)
    if len(content) < 3:
        await message.answer("❗ محتوای تسک خیلی کوتاه است. حداقل ۳ کاراکتر وارد کنید.")
        return

    await state.update_data(content=content)
    await state.set_state(AddTask.waiting_for_due_date)
    await message.answer("⏰ زمان انجام تسک را انتخاب کنید:", reply_markup=_due_keyboard())


# ───────────────────────────────
# ⏰ مرحله 3: انتخاب تاریخ از کیبورد
# ───────────────────────────────
@router.callback_query(F.data.startswith("due:"))
async def handle_due_selection(callback: CallbackQuery, state: FSMContext) -> None:
    choice = callback.data.split(":", 1)[1]
    now = _now_local()

    # پیش‌فرض: بدون تاریخ
    due_local: Optional[datetime] = None

    match choice:
        case "today":
            due_local = now.replace(hour=21, minute=0, second=0, microsecond=0)
        case "tomorrow":
            due_local = (now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        case "urgent":
            due_local = now + timedelta(hours=2)
        case "week":
            days_to_sun = (6 - now.weekday()) % 7  # Monday=0 ... Sunday=6
            due_local = (now + timedelta(days=days_to_sun)).replace(hour=23, minute=0, second=0, microsecond=0)
        case "none":
            due_local = None
        case "manual":
            await callback.message.answer(
                "📅 تاریخ دلخواه را وارد کنید:\n"
                "• 2025-09-15\n"
                "• 2025-09-15 14:30\n"
                "• 15.09.2025\n"
                "• 15.09.2025 14:30\n"
                "• 2025/09/15"
            )
            await state.set_state(AddTask.waiting_for_custom_date)
            await callback.answer()
            return
        case _:
            logger.warning("⚠️ INVALID DATE choice=%r user=%s", choice, callback.from_user.id)
            await callback.answer("❗ تاریخ نامعتبر است.")
            return

    await state.update_data(due_date=_to_utc(due_local))
    await state.set_state(AddTask.waiting_for_priority)

    # بستن UI لودینگ و حرکت به اولویت — کیبورد با زبان کاربر
    await callback.answer()
    await callback.message.answer(
        "📌 لطفاً اولویت تسک را انتخاب کنید:",
        reply_markup=priority_keyboard(lang=_lang_of(callback.from_user)),
    )


# ───────────────────────────────
# 🗓 مرحله 3.5: دریافت تاریخ دستی
# ───────────────────────────────
@router.message(AddTask.waiting_for_custom_date, F.text)
async def receive_custom_date(message: Message, state: FSMContext) -> None:
    parsed = _parse_custom_date(message.text)
    if not parsed:
        await message.answer("❗ فرمت اشتباه است. مثال: 2025-09-15 یا 2025-09-15 14:30")
        return

    # جلوگیری از تاریخ گذشته (فقط تاریخ؛ اگر ساعت هم دادی، همین چک ساده کافیه)
    if parsed.date() < _now_local().date():
        await message.answer("⚠️ تاریخ گذشته است. لطفاً تاریخ آینده وارد کنید.")
        return

    await state.update_data(due_date=_to_utc(parsed))
    await state.set_state(AddTask.waiting_for_priority)
    await message.answer(
        "📌 حالا لطفاً اولویت تسک را انتخاب کنید:",
        reply_markup=priority_keyboard(lang=_lang_of(message.from_user)),
    )


# ───────────────────────────────
# 🚦 مرحله 4: انتخاب اولویت
# ───────────────────────────────
@router.callback_query(F.data.startswith("priority:"))
async def handle_priority_selection(callback: CallbackQuery, state: FSMContext) -> None:
    priority = parse_priority_from_callback(callback.data, prefix="priority:")
    if priority is None:
        logger.warning("❗ INVALID PRIORITY user=%s data=%r", callback.from_user.id, callback.data)
        await callback.answer("❗ اولویت نامعتبر است.")
        return

    # ذخیره به‌صورت name (HIGH/MEDIUM/LOW) در state
    await state.update_data(priority=priority.name)

    # تایید انتخاب به زبان کاربر
    await callback.answer()
    await callback.message.answer(
        f"✅ اولویت انتخاب شد: {priority_label(priority, lang=_lang_of(callback.from_user))}"
    )

    await _save_task(callback, state)


# ───────────────────────────────
# 💾 مرحله نهایی: ذخیره تسک
# ───────────────────────────────
async def _save_task(source: Message | CallbackQuery, state: FSMContext) -> None:
    user_info = source.from_user
    data = await state.get_data()

    content = data.get("content")
    due_date_utc = data.get("due_date")  # باید datetime-aware (UTC) باشد یا None
    priority_str = (data.get("priority") or "MEDIUM").upper()

    if not content:
        await _safe_answer(source, "❗ خطا در دریافت محتوای تسک.")
        await state.clear()
        return

    try:
        priority = TaskPriority[priority_str]
    except Exception:
        logger.warning("❗ INVALID PRIORITY FALLBACK user=%s raw=%r", user_info.id, priority_str)
        priority = TaskPriority.MEDIUM

    async with transactional_session() as session:
        user = await create_or_update_user(
            session=session,
            telegram_id=user_info.id,
            full_name=user_info.full_name,
            username=user_info.username,
            language=_lang_of(user_info),
            commit=False,
        )
        if not user:
            logger.error("❌ USER CREATE/UPDATE FAILED tg=%s", user_info.id)
            await _safe_answer(source, "❗ حساب کاربری پیدا نشد. لطفاً /start را بزنید.")
            await state.clear()
            return

        task = await create_task(
            session=session,
            user_id=user.id,
            content=content,
            due_date=due_date_utc,
            priority=priority,
            commit=False,  # در transactional_session اتمیک کمیت می‌شود
        )

        if task:
            await _safe_answer(source, "✅ تسک با موفقیت ثبت شد!")
            logger.info("📌 TASK CREATED tg=%s task_id=%s", user_info.id, task.id)
        else:
            logger.error("❌ TASK CREATION FAILED tg=%s", user_info.id)
            await _safe_answer(source, "❌ ذخیره تسک ناموفق بود.")

    # پاکسازی state و بازگشت به منو
    await state.clear()
    await _safe_answer(source, "🏠 برگشت به منوی اصلی:", reply_markup=main_menu_keyboard())
