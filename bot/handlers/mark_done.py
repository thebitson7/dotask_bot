# bot/handlers/mark_done.py
from __future__ import annotations

import logging
from html import escape
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from core.config import get_settings
from database.session import transactional_session
from database.crud import create_or_update_user, mark_task_as_done

router = Router()
logger = logging.getLogger(__name__)
settings = get_settings()
LOCAL_TZ = ZoneInfo(settings.TZ)

# ─────────────────────────────────────────────
# 🔧 Helpers
# ─────────────────────────────────────────────
def _extract_task_id(cb_data: str, prefix: str = "done:") -> Optional[int]:
    if not cb_data or not cb_data.startswith(prefix):
        return None
    _, _, tail = cb_data.partition(":")
    try:
        return int(tail)
    except (TypeError, ValueError):
        return None


async def _safe_answer(cb: CallbackQuery, text: str, **kwargs) -> None:
    try:
        await cb.answer(text, **kwargs)
    except Exception as e:  # pragma: no cover
        logger.debug("Callback answer failed: %s", e)


def _to_local(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        # دیتابیس شما UTC-aware است؛ ولی اگر نبود، محلی فرض می‌کنیم
        return dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(LOCAL_TZ)


def _fmt(dt: Optional[datetime], with_time: bool = True) -> str:
    if dt is None:
        return "بدون تاریخ"
    dt = _to_local(dt)
    return dt.strftime("%Y-%m-%d %H:%M") if with_time else dt.strftime("%Y-%m-%d")


def _render_done_message(content: str, due_date: Optional[datetime], done_at: Optional[datetime]) -> str:
    safe_content = escape(content)
    due = _fmt(due_date, with_time=False)
    done = _fmt(done_at, with_time=True) if done_at else "—"
    return (
        f"✅ <b>{safe_content}</b>\n"
        f"⏰ {due} | ✅ انجام شده در {done}"
    )


# ─────────────────────────────────────────────
# ✅ هندلر دکمه «انجام شد»
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("done:"))
async def handle_mark_task_done(callback: CallbackQuery) -> None:
    user = callback.from_user
    task_id = _extract_task_id(callback.data)

    if task_id is None:
        logger.warning("⚠️ INVALID TASK_ID user=%s data=%r", user.id, callback.data)
        await _safe_answer(callback, "❗ شناسه تسک معتبر نیست.", show_alert=True)
        return

    try:
        async with transactional_session() as session:
            # اطمینان از وجود/به‌روزرسانی کاربر
            db_user = await create_or_update_user(
                session=session,
                telegram_id=user.id,
                full_name=user.full_name,
                username=user.username,
                language=user.language_code or settings.DEFAULT_LANG,
                commit=False,  # در transactional_session کمیت انجام می‌شود
            )
            if not db_user:
                logger.error("❌ USER NOT FOUND/CREATED tg=%s", user.id)
                await _safe_answer(callback, "❗ حساب کاربری پیدا نشد. لطفاً /start را بزن.", show_alert=True)
                return

            # علامت‌گذاری به‌صورت idempotent
            task = await mark_task_as_done(
                session=session,
                user_id=db_user.id,
                task_id=task_id,
                commit=False,  # اتمیک
            )

        if not task:
            logger.info("ℹ️ TASK NOT FOUND OR NO ACCESS user=%s task=%s", user.id, task_id)
            await _safe_answer(callback, "❌ تسک پیدا نشد یا قبلاً حذف شده.", show_alert=True)
            return

        # پیام بازخورد خنثی (چه تازه انجام شده، چه قبلاً انجام بوده)
        await _safe_answer(callback, "✅ وضعیت تسک: انجام‌شده.")

        # تلاش برای پاک‌کردن کیبورد و ویرایش متن پیام
        try:
            await callback.message.edit_text(
                _render_done_message(task.content, task.due_date, task.done_at)
            )
        except TelegramBadRequest as e:
            # ممکن است پیام تغییر نکرده/حذف شده باشد — لاگ کم‌نویز
            if "message is not modified" not in str(e).lower():
                logger.debug("Edit failed: %s", e)
        except Exception as e:
            logger.debug("Message edit unexpected error: %s", e)

    except Exception as e:
        logger.exception("💥 ERROR @handle_mark_task_done user=%s task=%s -> %s", user.id, task_id, e)
        await _safe_answer(callback, "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کن.", show_alert=True)
