# bot/handlers/start.py
from __future__ import annotations

import logging
from html import escape
from typing import Optional

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from core.config import get_settings
from bot.keyboards.main_menu import main_menu_keyboard
from database.session import transactional_session, get_session
from database import crud

router = Router()
logger = logging.getLogger(__name__)
settings = get_settings()


def _lang(user) -> str:
    """fa/en با fallback به تنظیمات."""
    return (getattr(user, "language_code", None) or settings.DEFAULT_LANG or "fa").lower()


def _mk_welcome_fa(first_name: Optional[str], open_count: int, done_count: int, payload: Optional[str]) -> str:
    name = escape(first_name or "")
    intro = f"<b>🎉 خوش اومدی{name and f'، {name}' or ''}!</b>\nمن اینجام که کمکت کنم تسک‌هات رو سریع و خوشگل مدیریت کنی. 🧠"
    stats = f"\n\n📊 وضعیت فعلی تو:\n• باز: <b>{open_count}</b>\n• انجام‌شده: <b>{done_count}</b>"
    hint_payload = ""
    if payload:
        hint_payload = (
            "\n\n🧲 لینک ورودی تشخیص داده شد — اگر می‌خوای همون متنو به‌عنوان تسک ذخیره کنی، "
            "روی «➕ افزودن تسک» بزن و همونو بفرست."
        )
    actions = (
        "\n\n⬇️ از اینجا شروع کن:\n"
        "• «➕ افزودن تسک» برای ساخت سریع\n"
        "• «📋 لیست تسک‌ها» برای مرور و مدیریت\n"
        "• «🔎 جستجو» برای پیدا کردن فوری\n"
        "• «⚙️ تنظیمات» برای شخصی‌سازی"
    )
    cta = "\n\n👇 یکی از گزینه‌ها رو انتخاب کن:"
    return f"{intro}{stats}{hint_payload}{actions}{cta}"


def _mk_welcome_en(first_name: Optional[str], open_count: int, done_count: int, payload: Optional[str]) -> str:
    name = escape(first_name or "")
    intro = f"<b>🎉 Welcome{name and f', {name}' or ''}!</b>\nI’m here to help you manage tasks fast and beautifully. 🧠"
    stats = f"\n\n📊 Your current status:\n• Open: <b>{open_count}</b>\n• Done: <b>{done_count}</b>"
    hint_payload = ""
    if payload:
        hint_payload = (
            "\n\n🧲 Deep-link detected — if you want to save that text as a task, "
            "tap “➕ Add Task” and send it."
        )
    actions = (
        "\n\n⬇️ Start here:\n"
        "• “➕ Add Task” to create quickly\n"
        "• “📋 Tasks” to browse & manage\n"
        "• “🔎 Search” to find instantly\n"
        "• “⚙️ Settings” to customize"
    )
    cta = "\n\n👇 Pick an option:"
    return f"{intro}{stats}{hint_payload}{actions}{cta}"


def _extract_start_payload(text: Optional[str]) -> Optional[str]:
    """
    /start payload را اگر وجود داشت برمی‌گرداند.
    مثال‌ها:
      /start
      /start add
      /start buy-milk
    """
    if not text:
        return None
    parts = text.strip().split(maxsplit=1)
    if len(parts) == 2 and parts[0].startswith("/start"):
        return parts[1].strip() or None
    return None


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    user = message.from_user
    lang = _lang(user)
    payload = _extract_start_payload(message.text)

    logger.info("[👋 /start] user=%s (%s) payload=%r", user.full_name, user.id, payload)

    # 1) تضمین کاربر + گرفتن آمار
    open_count = done_count = 0
    try:
        async with transactional_session() as session:
            # ensure/create user
            db_user = await crud.create_or_update_user(
                session=session,
                telegram_id=user.id,
                full_name=user.full_name,
                username=user.username,
                language=lang,
                commit=False,  # transactional_session کمیت می‌کند
            )
        # count (خارج از تراکنش جدا، read-only)
        async with get_session() as rsession:
            open_count, done_count = await crud.count_tasks_by_status(rsession, user_id=db_user.id)  # type: ignore[attr-defined]
    except Exception:
        logger.exception("[/start] ensure/count failed; continue with defaults.")

    # 2) ساخت کیبورد
    try:
        kb = main_menu_keyboard()
    except Exception:
        logger.exception("[/start] main_menu_keyboard failed; fallback to None.")
        kb = None

    # 3) متن خوش‌آمد
    welcome = (
        _mk_welcome_fa(user.first_name, open_count, done_count, payload)
        if lang.startswith("fa")
        else _mk_welcome_en(user.first_name, open_count, done_count, payload)
    )

    # 4) ارسال پیام
    try:
        await message.answer(welcome, reply_markup=kb)
        logger.info("[/start] welcome message sent.")
    except TelegramBadRequest as e:
        logger.warning("[/start] TelegramBadRequest: %s → sending plain fallback", e)
        # نسخهٔ ساده بدون HTML/کیبورد
        try:
            if lang.startswith("fa"):
                await message.answer(
                    "🎉 خوش اومدی!\n"
                    f"باز: {open_count} | انجام‌شده: {done_count}\n"
                    "از منوی پایین یکی رو انتخاب کن."
                )
            else:
                await message.answer(
                    "🎉 Welcome!\n"
                    f"Open: {open_count} | Done: {done_count}\n"
                    "Pick an option from the menu below."
                )
        except Exception:
            logger.exception("[/start] plain fallback failed.")
            await message.answer("❌ خطا در ارسال پیام. لطفاً بعداً تلاش کن.")
    except Exception:
        logger.exception("[/start] unexpected send error.")
        await message.answer("❌ خطا در ارسال پیام. لطفاً بعداً تلاش کن.")
