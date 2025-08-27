from aiogram import Router, F
from aiogram.types import CallbackQuery
from database.session import get_session
from database.crud import create_or_update_user, mark_task_as_done
import logging

router = Router()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# ✅ هندلر دکمه "انجام شد"
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("done:"))
async def handle_mark_task_done(callback: CallbackQuery) -> None:
    user_info = callback.from_user
    user_id = user_info.id
    callback_data = callback.data

    task_id = extract_task_id(callback_data)
    if task_id is None:
        logger.warning(f"[⚠️ INVALID TASK_ID] user_id={user_id}, data={callback_data}")
        await callback.answer("❗ شناسه تسک معتبر نیست.", show_alert=True)
        return

    try:
        async with get_session() as session:
            # 📦 اطمینان از وجود کاربر
            user = await create_or_update_user(
                session=session,
                telegram_id=user_info.id,
                full_name=user_info.full_name,
                username=user_info.username,
                language=user_info.language_code or "fa"
            )

            if not user:
                logger.error(f"[❌ USER NOT FOUND] telegram_id={user_id}")
                await callback.answer("❗ حساب کاربری پیدا نشد. لطفاً /start را بزن.", show_alert=True)
                return

            # ✅ علامت‌گذاری تسک به عنوان انجام‌شده
            task = await mark_task_as_done(session, user_id=user.id, task_id=task_id)

            if not task:
                logger.warning(f"[⚠️ TASK NOT FOUND OR ALREADY DONE] user_id={user_id}, task_id={task_id}")
                await callback.answer("❌ تسک پیدا نشد یا قبلاً انجام شده.", show_alert=True)
                return

            logger.info(f"[✅ TASK MARKED DONE] user_id={user_id}, task_id={task.id}")
            await callback.answer("✅ تسک با موفقیت انجام شد!")

            # ✏️ آپدیت پیام
            updated_text = (
                f"✅ <b>{task.content}</b>\n"
                f"⏰ {task.due_date.strftime('%Y-%m-%d') if task.due_date else 'بدون تاریخ'} | ✅ انجام شده"
            )

            try:
                await callback.message.edit_text(updated_text)
            except Exception as edit_error:
                logger.warning(f"[⚠️ MESSAGE EDIT FAILED] task_id={task_id}, error={edit_error}")

    except Exception as e:
        logger.exception(f"[💥 ERROR @ handle_mark_task_done] user_id={user_id} -> {e}")
        await callback.answer("⚠️ خطایی رخ داد. لطفاً مجدداً تلاش کن.", show_alert=True)


# ─────────────────────────────────────────────
# 🔧 استخراج امن task_id از callback_data
# ─────────────────────────────────────────────
def extract_task_id(callback_data: str) -> int | None:
    try:
        return int(callback_data.split(":")[1])
    except (IndexError, ValueError):
        return None
