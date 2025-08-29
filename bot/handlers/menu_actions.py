# bot/handlers/menu.py
from __future__ import annotations

import asyncio
import logging
from html import escape
from typing import Optional, Iterable
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.config import get_settings
from bot.keyboards.main_menu import (
    main_menu_keyboard,
    ADD_TASK_ALIASES,
    LIST_TASKS_ALIASES,
    SETTINGS_ALIASES,
    HELP_ALIASES,
)
from bot.utils.text_match import matches_any, normalize_text
from database.session import get_session, transactional_session
from database.crud import create_or_update_user, get_tasks_by_user_id
from database.models import Task

router = Router()
logger = logging.getLogger(__name__)
settings = get_settings()

# ─────────────────────────────────────────────
# ⚙️ Display & UX
# ─────────────────────────────────────────────
LOCAL_TZ = ZoneInfo(settings.TZ)
MAX_LINES_PER_MSG = 30         # حداکثر خطوط هر پیام
BATCH_SLEEP_SECONDS = 0.04     # فاصله بین پیام‌ها برای جلوگیری از Flood
CONTENT_MAX_INLINE = 120       # حداکثر طول نمایش عنوان
PRIO_EMOJI = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}

# ─────────────────────────────────────────────
# 🔧 Helpers
# ─────────────────────────────────────────────
def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else (text[: limit - 1] + "…")

def _to_local(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return (dt.replace(tzinfo=LOCAL_TZ) if dt.tzinfo is None else dt.astimezone(LOCAL_TZ))

def _fmt_due(dt: Optional[datetime]) -> str:
    if dt is None:
        return "🕓 بدون تاریخ"
    dt = _to_local(dt)
    # اگر لحظه‌ای نیست، تاریخ+ساعت را نشان بده
    return f"⏰ {dt.strftime('%Y-%m-%d %H:%M')}"

def _render_line(i: int, t: Task) -> str:
    title = _truncate(escape(t.content or "بدون عنوان"), CONTENT_MAX_INLINE)
    status = "✅" if t.is_done else "🕒"
    prio = PRIO_EMOJI.get(getattr(t.priority, "name", str(t.priority)), "⚪")
    due = _fmt_due(t.due_date)
    return f"{i}. {prio} {title} | {status} | {due}"

async def _send_batched(message: Message, lines: Iterable[str]) -> None:
    batch: list[str] = []
    for line in lines:
        batch.append(line)
        if len(batch) >= MAX_LINES_PER_MSG:
            await message.answer("📋 لیست وظایف:\n" + "\n".join(batch))
            batch.clear()
            await asyncio.sleep(BATCH_SLEEP_SECONDS)
    if batch:
        await message.answer("📋 لیست وظایف:\n" + "\n".join(batch))

async def _ensure_user_id(tg_user) -> int | None:
    try:
        async with transactional_session() as session:
            u = await create_or_update_user(
                session=session,
                telegram_id=tg_user.id,
                full_name=tg_user.full_name,
                username=tg_user.username,
                language=tg_user.language_code or "fa",
                commit=False,  # transactional_session خودش commit می‌کند
            )
            return u.id if u else None
    except Exception:
        logger.exception("[menu] ensure_user failed tg=%s", tg_user.id)
        return None

# ─────────────────────────────────────────────
# ➕ Add task (راهنما/ورود)
# ─────────────────────────────────────────────
@router.message(F.text.func(lambda t: matches_any(t, ADD_TASK_ALIASES)))
async def on_add_task(message: Message):
    logger.info("[menu] AddTask clicked by %s -> text='%s'", message.from_user.id, normalize_text(message.text))
    await message.answer(
        "➕ ایجاد تسک جدید:\n"
        "متن تسک را بفرست. بعدش زمان انجام و اولویت را از منو انتخاب می‌کنی.\n"
        "مثال: «خرید شیر»",
        reply_markup=main_menu_keyboard(),
    )

# ─────────────────────────────────────────────
# 📋 List tasks
# ─────────────────────────────────────────────
@router.message(F.text.func(lambda t: matches_any(t, LIST_TASKS_ALIASES)))
async def on_list_tasks(message: Message):
    user = message.from_user
    logger.info("[menu] ListTasks clicked by %s -> text='%s'", user.id, normalize_text(message.text))

    uid = await _ensure_user_id(user)
    if not uid:
        await message.answer("❗ حساب شما شناسایی نشد. /start را بزنید.", reply_markup=main_menu_keyboard())
        return

    try:
        # ابتدا بازها، سپس انجام‌شده‌ها
        async with get_session() as session:
            open_tasks = await get_tasks_by_user_id(session, user_id=uid, is_done=False, limit=100)
            done_tasks = await get_tasks_by_user_id(session, user_id=uid, is_done=True, limit=100)

        tasks = list(open_tasks) + list(done_tasks)
        if not tasks:
            await message.answer("📭 هنوز هیچ تسکی ثبت نکردی.", reply_markup=main_menu_keyboard())
            return

        lines = [_render_line(i, t) for i, t in enumerate(tasks, start=1)]
        await _send_batched(message, lines)
        await message.answer("🔙 برگشت به منوی اصلی:", reply_markup=main_menu_keyboard())

    except Exception:
        logger.exception("[menu] get_tasks_by_user_id failed uid=%s", uid)
        await message.answer("⚠️ خطا در دریافت لیست وظایف.", reply_markup=main_menu_keyboard())

# ─────────────────────────────────────────────
# ⚙️ Settings (placeholder)
# ─────────────────────────────────────────────
@router.message(F.text.func(lambda t: matches_any(t, SETTINGS_ALIASES)))
async def on_settings(message: Message):
    logger.info("[menu] Settings clicked by %s", message.from_user.id)
    await message.answer("⚙️ تنظیمات به‌زودی…", reply_markup=main_menu_keyboard())

# ─────────────────────────────────────────────
# ℹ️ Help
# ─────────────────────────────────────────────
@router.message(F.text.func(lambda t: matches_any(t, HELP_ALIASES)))
async def on_help(message: Message):
    logger.info("[menu] Help clicked by %s", message.from_user.id)
    await message.answer(
        "ℹ️ راهنما:\n"
        "• ➕ افزودن تسک: ایجاد تسک جدید\n"
        "• 📋 لیست وظایف: نمایش تسک‌های ثبت‌شده\n",
        reply_markup=main_menu_keyboard(),
    )

# ─────────────────────────────────────────────
# 📝 Debug unmatched texts
# ─────────────────────────────────────────────
@router.message(F.text)
async def on_any_text(message: Message):
    logger.debug(
        "[menu] Unmatched text from %s: %r (norm=%r)",
        message.from_user.id,
        message.text,
        normalize_text(message.text),
    )
