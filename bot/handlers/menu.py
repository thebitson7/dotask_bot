# bot/handlers/menu.py
from __future__ import annotations

import asyncio
import logging
from html import escape
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.config import get_settings
from bot.keyboards.main_menu import main_menu_keyboard
from database.session import transactional_session, get_session
from database.crud import create_or_update_user, get_tasks_by_user_id
from database.models import Task

router = Router()
logger = logging.getLogger(__name__)
settings = get_settings()

# ─────────────────────────────────────────────
# ⚙️ تنظیمات نمایش
# ─────────────────────────────────────────────
LOCAL_TZ = ZoneInfo(settings.TZ)
CONTENT_MAX_INLINE = 120     # حداکثر طول نمایش متن تسک
BATCH_SLEEP_SECONDS = 0.05   # فاصله بین پیام‌ها برای جلوگیری از Flood
MAX_TASKS_PER_LIST = 50      # سقف تعداد آیتم‌هایی که در یک بار نشان می‌دهیم

PRIO_EMOJI = {
    "HIGH": "🔴",
    "MEDIUM": "🟡",
    "LOW": "🟢",
}
STATUS_EMOJI = {
    True: "✅ انجام‌شده",
    False: "🕒 در انتظار",
}

# تریگرهای رایج دکمه/پیام برای نمایش لیست
_LIST_TRIGGERS = {
    "📋 لیست تسک‌ها",
    "📋 نمایش تسک‌ها",
    "📋 تسک‌ها",
    "📋 لیست وظایف",
}

# ─────────────────────────────────────────────
# 🔧 کمکی‌ها
# ─────────────────────────────────────────────
def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _to_local(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        # اگر از DB بدون tz برگشته باشد، آن را محلی فرض می‌کنیم
        return dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(LOCAL_TZ)


def _fmt_due(dt: Optional[datetime]) -> str:
    if dt is None:
        return "🕓 بدون تاریخ"
    dt = _to_local(dt)
    # اگر ساعت صفر نبود، ساعت را هم نشان بده
    if dt.hour or dt.minute:
        return f"⏰ {dt.strftime('%Y-%m-%d %H:%M')}"
    return f"⏰ {dt.strftime('%Y-%m-%d')}"


def _is_overdue(task: Task) -> bool:
    if task.is_done or not task.due_date:
        return False
    now_local = datetime.now(tz=LOCAL_TZ)
    return _to_local(task.due_date) < now_local


def _task_inline_keyboard(task_id: int, is_done: bool) -> Optional[InlineKeyboardMarkup]:
    # برای سادگی در منو: فقط دکمه‌های انجام و حذف (ویرایش/اسنوز در هندلر لیست حرفه‌ای موجود است)
    builder = InlineKeyboardBuilder()
    if not is_done:
        builder.button(text="✅ انجام شد", callback_data=f"done:{task_id}")
    builder.button(text="🗑 حذف", callback_data=f"delete:{task_id}")
    builder.adjust(2 if not is_done else 1)
    return builder.as_markup()


def _render_task_text(task: Task, index: int) -> str:
    content_safe = escape(task.content or "❓ بدون عنوان")
    content_show = _truncate(content_safe, CONTENT_MAX_INLINE)

    due_part = _fmt_due(task.due_date)
    status_part = STATUS_EMOJI[task.is_done]
    prio = PRIO_EMOJI.get(getattr(task.priority, "name", str(task.priority)), "⚪")

    badges = []
    if _is_overdue(task):
        badges.append("⚠️ سررسید گذشته")

    badges_text = f" | {' · '.join(badges)}" if badges else ""
    # نمونه خروجی:
    # 1) 🔴 خرید نان
    # ⏰ 2025-09-15 12:00 | 🕒 در انتظار | ⚠️ سررسید گذشته
    return (
        f"<b>{index}) {prio} {content_show}</b>\n"
        f"{due_part} | {status_part}{badges_text}"
    )

# ─────────────────────────────────────────────
# ✅ اطمینان از وجود کاربر در دیتابیس
# ─────────────────────────────────────────────
async def _ensure_user_exists(user_data) -> Optional[int]:
    try:
        async with transactional_session() as session:
            user = await create_or_update_user(
                session=session,
                telegram_id=user_data.id,
                full_name=user_data.full_name,
                username=user_data.username,
                language=(user_data.language_code or settings.DEFAULT_LANG),
                commit=False,  # اتمیک
            )
            return user.id if user else None
    except Exception:
        logger.exception("💥 USER GET/CREATE ERROR user_id=%s", user_data.id)
        return None

# ─────────────────────────────────────────────
# 📋 نمایش لیست تسک‌ها
# ─────────────────────────────────────────────
@router.message(F.text.in_(_LIST_TRIGGERS))
async def handle_list_tasks(message: Message) -> None:
    user_info = message.from_user
    logger.info("📋 LIST TASKS REQUESTED user_id=%s", user_info.id)

    user_id = await _ensure_user_exists(user_info)
    if not user_id:
        await message.answer("❗ حساب شما شناسایی نشد. لطفاً /start را بزنید.")
        return

    try:
        async with get_session() as session:
            # با امضای جدید: is_done → False/True
            open_tasks = await get_tasks_by_user_id(
                session,
                user_id=user_id,
                is_done=False,
                limit=MAX_TASKS_PER_LIST,
            )
            done_tasks = await get_tasks_by_user_id(
                session,
                user_id=user_id,
                is_done=True,
                limit=MAX_TASKS_PER_LIST,
            )

        ordered: list[Task] = list(open_tasks) + list(done_tasks)
        if not ordered:
            await message.answer("📭 هنوز هیچ تسکی ثبت نکردی.", reply_markup=main_menu_keyboard())
            return

        # ارسال با فاصلهٔ کوتاه برای جلوگیری از Flood
        for idx, task in enumerate(ordered, start=1):
            try:
                await message.answer(
                    _render_task_text(task, idx),
                    reply_markup=_task_inline_keyboard(task.id, task.is_done),
                )
            except Exception as e:
                logger.warning("⚠️ FAILED TO SEND TASK task_id=%s -> %s", getattr(task, "id", "?"), e)
            await asyncio.sleep(BATCH_SLEEP_SECONDS)

        # اگر مجموع از سقف بیشتر باشد، پیام راهنما
        total_shown = len(ordered)
        if total_shown >= MAX_TASKS_PER_LIST:
            await message.answer(f"ℹ️ فقط {MAX_TASKS_PER_LIST} آیتم اخیر نمایش داده شد.")

        await message.answer("🔙 برگشت به منوی اصلی:", reply_markup=main_menu_keyboard())

    except Exception as e:
        logger.exception("💥 ERROR @handle_list_tasks user_id=%s -> %s", user_info.id, e)
        await message.answer("⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.", reply_markup=main_menu_keyboard())
