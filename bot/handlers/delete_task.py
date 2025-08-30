# bot/handlers/delete_task.py
from __future__ import annotations

import logging
from typing import Optional, Iterable

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import crud
from database.session import transactional_session

router = Router()
logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────
# ⚙️ Settings (lazy import تا مشکل import-order پیش نیاد)
# ───────────────────────────────────────────────────────────────
def _settings():
    from core.config import get_settings  # lazy import
    return get_settings()


# ───────────────────────────────────────────────────────────────
# 🧩 Utilities
# ───────────────────────────────────────────────────────────────
def _delete_confirmation_kb(task_id: int) -> InlineKeyboardMarkup:
    """دو دکمه در یک ردیف: بله/لغو"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ بله، حذف کن", callback_data=f"confirm_delete:{task_id}"),
            InlineKeyboardButton(text="❌ لغو", callback_data="cancel_delete"),
        ]]
    )


def _extract_task_id(callback_data: str, prefixes: Iterable[str]) -> Optional[int]:
    """
    شناسه را از هرکدام از پیشوندهای مجاز بیرون می‌کشد.
    پشتیبانی‌شده:
      - 'delete:<id>'
      - 'delete:<id>;s=o;...'
      - 'tact:del:<id>;...'
      - 'confirm_delete:<id>;...'
    """
    if not callback_data:
        return None
    for p in prefixes:
        if callback_data.startswith(p):
            tail = callback_data[len(p):]
            # اگر بعد از id پارامترهایی با ; آمدند، آن‌ها را جدا کن
            if ";" in tail:
                tail = tail.split(";", 1)[0]
            # اگر به هر دلیلی فرمت tact:del:<id>:... بود، باز هم با split ایمن می‌کنیم
            if ":" in tail and tail.isdigit() is False:
                # مثلاً "123:extra" → قبل از ':' را بگیر
                tail = tail.split(":", 1)[0]
            try:
                return int(tail)
            except (TypeError, ValueError):
                return None
    return None


async def _safe_cb_answer(cb: CallbackQuery, text: str = "", **kwargs) -> None:
    """answer() بی‌صدا، برای بستن لودینگ یا نمایش هشدار کوتاه."""
    try:
        await cb.answer(text, **kwargs)
    except Exception as e:  # pragma: no cover
        logger.debug("Callback answer failed: %s", e)


async def _edit_reply_markup_safely(cb: CallbackQuery, **kwargs) -> None:
    """ویرایش reply_markup بدون آلودگی لاگ با خطای message-not-modified."""
    try:
        await cb.message.edit_reply_markup(**kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.debug("edit_reply_markup failed: %s", e)
    except Exception as e:
        logger.debug("edit_reply_markup unexpected: %s", e)


async def _edit_text_safely(cb: CallbackQuery, text: str, **kwargs) -> None:
    """ویرایش متن پیام با هندل خطاهای رایج."""
    try:
        await cb.message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        # ممکن است پیام قبلاً تغییر کرده یا قابل ویرایش نباشد
        if "message is not modified" not in str(e).lower():
            logger.debug("edit_text failed: %s", e)
    except Exception as e:
        logger.debug("edit_text unexpected: %s", e)


# ───────────────────────────────────────────────────────────────
# 🗑️ مرحله ۱: درخواست حذف (سازگار با قدیمی و جدید)
#   - قدیمی:  delete:<id>
#   - جدید:   tact:del:<id>;s=...;p=...
# ───────────────────────────────────────────────────────────────
@router.callback_query(
    F.data.func(lambda d: bool(d) and (d.startswith("delete:") or d.startswith("tact:del:")))
)
async def confirm_delete(cb: CallbackQuery) -> None:
    task_id = _extract_task_id(cb.data, ("delete:", "tact:del:"))

    if task_id is None:
        logger.warning("⚠️ INVALID TASK ID user=%s data=%r", cb.from_user.id, cb.data)
        await _safe_cb_answer(cb, "❗ شناسهٔ تسک معتبر نیست.", show_alert=True)
        return

    # پاک‌کردن کیبورد پیام قبلی (اگر داشت) و نمایش تأییدیه
    await _edit_reply_markup_safely(cb, reply_markup=None)
    try:
        await cb.message.answer(
            "❓ آیا از حذف این تسک مطمئن هستید؟",
            reply_markup=_delete_confirmation_kb(task_id),
        )
        await _safe_cb_answer(cb)  # بستن لودینگ
    except Exception as e:
        logger.exception("💥 ERROR @confirm_delete user=%s task=%s -> %s", cb.from_user.id, task_id, e)
        await _safe_cb_answer(cb, "⚠️ مشکلی در نمایش تأییدیه حذف رخ داد.", show_alert=True)


# ───────────────────────────────────────────────────────────────
# ✅ مرحله ۲: تایید نهایی و حذف (اتمیک)
# ───────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("confirm_delete:"))
async def handle_confirm_delete(cb: CallbackQuery) -> None:
    task_id = _extract_task_id(cb.data, ("confirm_delete:",))
    if task_id is None:
        logger.warning("⚠️ INVALID CONFIRM FORMAT user=%s data=%r", cb.from_user.id, cb.data)
        await _safe_cb_answer(cb, "❗ شناسهٔ تسک معتبر نیست.", show_alert=True)
        return

    try:
        async with transactional_session() as session:
            # اطمینان از وجود/به‌روزرسانی کاربر
            user = await crud.create_or_update_user(
                session=session,
                telegram_id=cb.from_user.id,
                full_name=cb.from_user.full_name,
                username=cb.from_user.username,
                language=(cb.from_user.language_code or _settings().DEFAULT_LANG),
                commit=False,  # transactional_session خودش commit می‌کند
            )
            if not user:
                logger.error("❌ USER NOT FOUND/CREATED tg=%s", cb.from_user.id)
                await _safe_cb_answer(cb, "❗ حساب کاربری پیدا نشد. لطفاً /start را بزنید.", show_alert=True)
                return

            deleted = await crud.delete_task_by_id(
                session=session,
                user_id=user.id,
                task_id=task_id,
                commit=False,  # اتمیک
            )

        if not deleted:
            logger.info("ℹ️ DELETE NO-OP user=%s task_id=%s (not found or no access)", cb.from_user.id, task_id)
            await _safe_cb_answer(cb, "❌ تسک یافت نشد یا قبلاً حذف شده.", show_alert=True)
            return

        logger.info("🗑️ TASK DELETED user=%s task_id=%s", cb.from_user.id, task_id)
        await _edit_text_safely(cb, "🗑️ تسک با موفقیت حذف شد.")
        await _safe_cb_answer(cb)

    except Exception as e:
        logger.exception("💥 ERROR @handle_confirm_delete user=%s task=%s -> %s", cb.from_user.id, task_id, e)
        await _safe_cb_answer(cb, "⚠️ خطایی در حذف تسک رخ داد.", show_alert=True)


# ───────────────────────────────────────────────────────────────
# ❌ مرحله ۳: لغو عملیات حذف
# ───────────────────────────────────────────────────────────────
@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(cb: CallbackQuery) -> None:
    await _edit_reply_markup_safely(cb, reply_markup=None)
    await _safe_cb_answer(cb, "❌ عملیات حذف لغو شد.")
