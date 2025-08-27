from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.session import get_session
from database.crud import create_or_update_user, delete_task_by_id
import logging

router = Router()
logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────
# 🧩 ساخت کیبورد تایید حذف تسک
# ───────────────────────────────────────────────────────────────
def create_delete_confirmation_keyboard(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ بله، حذف کن", callback_data=f"confirm_delete:{task_id}"),
            InlineKeyboardButton(text="❌ لغو", callback_data="cancel_delete")
        ]
    ])


# ───────────────────────────────────────────────────────────────
# 🧠 استخراج امن task_id از callback_data
# ───────────────────────────────────────────────────────────────
def extract_task_id(callback_data: str, prefix: str) -> int | None:
    try:
        if not callback_data.startswith(prefix):
            return None
        return int(callback_data.split(":")[1])
    except (IndexError, ValueError):
        return None


# ───────────────────────────────────────────────────────────────
# 🗑️ مرحله ۱: درخواست حذف و نمایش تاییدیه
# ───────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("delete:"))
async def confirm_delete(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    task_id = extract_task_id(callback.data, "delete:")

    if task_id is None:
        logger.warning(f"[⚠️ INVALID TASK ID] user_id={user_id}, data={callback.data}")
        await callback.answer("❗ شناسه تسک معتبر نیست.", show_alert=True)
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "❓ آیا از حذف این تسک مطمئنی؟",
            reply_markup=create_delete_confirmation_keyboard(task_id)
        )
        await callback.answer()
    except Exception as e:
        logger.exception(f"[💥 ERROR @ confirm_delete] user={user_id} -> {e}")
        await callback.answer("⚠️ مشکلی پیش آمد. لطفاً دوباره امتحان کن.", show_alert=True)


# ───────────────────────────────────────────────────────────────
# ✅ مرحله ۲: تایید نهایی و حذف تسک
# ───────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("confirm_delete:"))
async def handle_confirm_delete(callback: CallbackQuery) -> None:
    user_info = callback.from_user
    user_id = user_info.id
    task_id = extract_task_id(callback.data, "confirm_delete:")

    if task_id is None:
        logger.warning(f"[⚠️ INVALID CALLBACK FORMAT] user_id={user_id}, data={callback.data}")
        await callback.answer("❗ شناسه تسک معتبر نیست.", show_alert=True)
        return

    try:
        async with get_session() as session:
            user = await create_or_update_user(
                session=session,
                telegram_id=user_info.id,
                full_name=user_info.full_name,
                username=user_info.username,
                language=user_info.language_code or "fa"
            )

            if not user:
                logger.warning(f"[❌ USER NOT FOUND] telegram_id={user_id}")
                await callback.answer("❗ حساب شما پیدا نشد. لطفاً /start را بزن.", show_alert=True)
                return

            deleted = await delete_task_by_id(session, user_id=user.id, task_id=task_id)

            if not deleted:
                logger.warning(f"[⚠️ DELETE FAILED] user_id={user_id}, task_id={task_id}")
                await callback.answer("❌ تسک یافت نشد یا قابل حذف نیست.", show_alert=True)
                return

            logger.info(f"[🗑️ TASK DELETED] user_id={user_id}, task_id={task_id}")
            await callback.message.edit_text("🗑️ تسک با موفقیت حذف شد.")
            await callback.answer()

    except Exception as e:
        logger.exception(f"[💥 ERROR @ delete_task] user={user_id} -> {e}")
        await callback.answer("⚠️ خطایی در حذف تسک رخ داد.", show_alert=True)


# ───────────────────────────────────────────────────────────────
# ❌ مرحله ۳: لغو عملیات حذف
# ───────────────────────────────────────────────────────────────
@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery) -> None:
    try:
        await callback.message.delete()
        await callback.answer("❌ عملیات حذف لغو شد.")
    except Exception as e:
        logger.warning(f"[⚠️ CANCEL DELETE FAILED] user_id={callback.from_user.id} -> {e}")
        await callback.answer("⚠️ مشکلی در لغو رخ داد.")
