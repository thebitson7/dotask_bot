# bot/handlers/delete_task.py
from __future__ import annotations

import logging
from typing import Optional

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import get_settings
from database.crud import create_or_update_user, delete_task_by_id
from database.session import transactional_session

router = Router()
logger = logging.getLogger(__name__)
settings = get_settings()

# ───────────────────────────────────────────────────────────────
# 🧩 ساخت کیبورد تایید حذف تسک
# ───────────────────────────────────────────────────────────────
def _delete_confirmation_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[  # 2 buttons in one row
        [
            InlineKeyboardButton(text="✅ بله، حذف کن", callback_data=f"confirm_delete:{task_id}"),
            InlineKeyboardButton(text="❌ لغو", callback_data="cancel_delete"),
        ]
    ])


# ───────────────────────────────────────────────────────────────
# 🧠 استخراج امن task_id از callback_data
# ───────────────────────────────────────────────────────────────
def _extract_task_id(callback_data: str, prefix: str) -> Optional[int]:
    if not callback_data or not callback_data.startswith(prefix):
        return None
    _, _, tail = callback_data.partition(":")
    try:
        return int(tail)
    except (TypeError, ValueError):
        return None


async def _safe_answer(cb: CallbackQuery, text: str, **kwargs) -> None:
    try:
        await cb.answer(text, **kwargs)
    except Exception as e:  # pragma: no cover
        logger.debug("Failed to answer callback: %s", e)


# ───────────────────────────────────────────────────────────────
# 🗑️ مرحله ۱: درخواست حذف و نمایش تاییدیه
# ───────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("delete:"))
async def confirm_delete(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    task_id = _extract_task_id(callback.data, "delete:")

    if task_id is None:
        logger.warning("⚠️ INVALID TASK ID user_id=%s data=%r", user_id, callback.data)
        await _safe_answer(callback, "❗ شناسه تسک معتبر نیست.", show_alert=True)
        return

    # حذف کیبورد قبلی (اگر وجود داشته باشد) و نمایش تاییدیه
    try:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest as e:
            # Message is not modified / message has no inline keyboard — مشکلی نیست
            if "message is not modified" not in str(e).lower():
                raise
        await callback.message.answer(
            "❓ آیا از حذف این تسک مطمئن هستید؟",
            reply_markup=_delete_confirmation_kb(task_id),
        )
        await _safe_answer(callback, "")
    except Exception as e:
        logger.exception("💥 ERROR @confirm_delete user=%s task=%s -> %s", user_id, task_id, e)
        await _safe_answer(callback, "⚠️ مشکلی در نمایش تاییدیه حذف رخ داد.", show_alert=True)


# ───────────────────────────────────────────────────────────────
# ✅ مرحله ۲: تایید نهایی و حذف تسک (اتمیک)
# ───────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("confirm_delete:"))
async def handle_confirm_delete(callback: CallbackQuery) -> None:
    user = callback.from_user
    task_id = _extract_task_id(callback.data, "confirm_delete:")

    if task_id is None:
        logger.warning("⚠️ INVALID CALLBACK FORMAT user=%s data=%r", user.id, callback.data)
        await _safe_answer(callback, "❗ شناسه تسک معتبر نیست.", show_alert=True)
        return

    try:
        async with transactional_session() as session:
            # اطمینان از وجود/به‌روزرسانی کاربر (در صورت اولین تعامل)
            db_user = await create_or_update_user(
                session=session,
                telegram_id=user.id,
                full_name=user.full_name,
                username=user.username,
                language=user.language_code or settings.DEFAULT_LANG,
                commit=False,  # transactional_session خودش commit می‌کند
            )
            if not db_user:
                logger.error("❌ USER NOT FOUND/CREATED tg=%s", user.id)
                await _safe_answer(callback, "❗ حساب کاربری پیدا نشد. لطفاً /start را بزنید.", show_alert=True)
                return

            deleted = await delete_task_by_id(
                session=session,
                user_id=db_user.id,
                task_id=task_id,
                commit=False,  # اتمیک
            )

        if not deleted:
            logger.info("ℹ️ DELETE NO-OP user=%s task_id=%s (not found)", user.id, task_id)
            await _safe_answer(callback, "❌ تسک یافت نشد یا قبلاً حذف شده.", show_alert=True)
            return

        logger.info("🗑️ TASK DELETED user=%s task_id=%s", user.id, task_id)

        # ویرایش پیام تایید به نتیجهٔ نهایی
        try:
            await callback.message.edit_text("🗑️ تسک با موفقیت حذف شد.")
        except TelegramBadRequest as e:
            # ممکن است پیام بین این دو مرحله حذف/تغییر یافته باشد
            logger.debug("Edit text failed after delete: %s", e)

        await _safe_answer(callback, "")

    except Exception as e:
        logger.exception("💥 ERROR @handle_confirm_delete user=%s task=%s -> %s", user.id, task_id, e)
        await _safe_answer(callback, "⚠️ خطایی در حذف تسک رخ داد.", show_alert=True)


# ───────────────────────────────────────────────────────────────
# ❌ مرحله ۳: لغو عملیات حذف
# ───────────────────────────────────────────────────────────────
@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery) -> None:
    try:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e).lower():
                raise
        await _safe_answer(callback, "❌ عملیات حذف لغو شد.")
    except Exception as e:
        logger.warning("⚠️ CANCEL DELETE FAILED user=%s -> %s", callback.from_user.id, e)
        await _safe_answer(callback, "⚠️ مشکلی در لغو عملیات رخ داد.")
