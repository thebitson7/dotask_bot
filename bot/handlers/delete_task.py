# bot/handlers/delete_task.py

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.session import get_session
from database.crud import get_user_by_telegram_id, delete_task_by_id
import logging

router = Router()
logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────
# 🧩 ساخت کیبورد تأیید حذف تسک
# ───────────────────────────────────────────────
def create_delete_confirmation_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """
    ساخت کیبورد تأیید برای حذف تسک خاص
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ بله، حذف کن",
                callback_data=f"confirm_delete:{task_id}"
            ),
            InlineKeyboardButton(
                text="❌ لغو",
                callback_data="cancel_delete"
            )
        ]
    ])


# ───────────────────────────────────────────────
# 🗑️ مرحله اول: دریافت درخواست حذف و ارسال تأییدیه
# ───────────────────────────────────────────────
@router.callback_query(lambda c: c.data and c.data.startswith("delete:"))
async def confirm_delete(callback: CallbackQuery):
    """
    مرحله تأیید حذف پس از کلیک روی دکمه حذف
    """
    try:
        raw_task_id = callback.data.split(":")[1]
        if not raw_task_id.isdigit():
            await callback.answer("❗ شناسه تسک نامعتبر است.", show_alert=True)
            return

        task_id = int(raw_task_id)

        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "❓ آیا از حذف این تسک مطمئنی؟",
            reply_markup=create_delete_confirmation_keyboard(task_id)
        )

    except Exception as e:
        logger.exception(f"[💥 ERROR @ confirm_delete] {e}")
        await callback.answer("⚠️ مشکلی پیش آمد.")


# ───────────────────────────────────────────────
# ✅ مرحله دوم: تأیید نهایی و حذف تسک
# ───────────────────────────────────────────────
@router.callback_query(lambda c: c.data and c.data.startswith("confirm_delete:"))
async def handle_confirm_delete(callback: CallbackQuery):
    """
    حذف واقعی تسک پس از تأیید کاربر
    """
    user_id = callback.from_user.id
    try:
        task_id = int(callback.data.split(":")[1])

        async with get_session() as session:
            user = await get_user_by_telegram_id(session, telegram_id=user_id)

            if not user:
                logger.warning(f"[❌ USER NOT FOUND] user_id={user_id}")
                await callback.answer("❗ کاربر شناسایی نشد.", show_alert=True)
                return

            success = await delete_task_by_id(session, user_id=user.id, task_id=task_id)

            if success:
                logger.info(f"[🗑️ TASK DELETED] user_id={user_id}, task_id={task_id}")
                await callback.answer("🗑️ تسک با موفقیت حذف شد.")
                await callback.message.edit_text("🗑️ تسک حذف شد.")
            else:
                logger.warning(f"[⚠️ DELETE FAILED] user_id={user_id}, task_id={task_id}")
                await callback.answer("❌ تسک یافت نشد یا مجاز به حذف آن نیستی.", show_alert=True)

    except Exception as e:
        logger.exception(f"[💥 ERROR @ delete_task] user={user_id}, error={e}")
        await callback.answer("⚠️ خطایی در حذف تسک رخ داد.", show_alert=True)


# ───────────────────────────────────────────────
# ❌ لغو عملیات حذف توسط کاربر
# ───────────────────────────────────────────────
@router.callback_query(lambda c: c.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    """
    لغو عملیات حذف تسک
    """
    await callback.answer("❌ عملیات حذف لغو شد.")
    await callback.message.delete()
