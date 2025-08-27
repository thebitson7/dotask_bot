from aiogram import Router
from aiogram.types import CallbackQuery
from database.session import get_session
from database.crud import create_or_update_user, mark_task_as_done
import logging

router = Router()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# ✅ هندلر کلیک روی دکمه "انجام شد"
# ─────────────────────────────────────────────
@router.callback_query(lambda c: c.data and c.data.startswith("done:"))
async def handle_mark_task_done(callback: CallbackQuery) -> None:
    user_info = callback.from_user
    user_id = user_info.id
    callback_data = callback.data

    try:
        # 🧩 استخراج task_id
        task_id = extract_task_id(callback_data)
        if task_id is None:
            await callback.answer("❗ شناسه تسک معتبر نیست.", show_alert=True)
            return

        # 📦 اطمینان از وجود کاربر
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
                await callback.answer("❗ حساب کاربری پیدا نشد. لطفاً /start را بزن.", show_alert=True)
                return

            # 🎯 مارک کردن تسک
            task = await mark_task_as_done(session, user_id=user.id, task_id=task_id)

            if not task:
                logger.info(f"[⚠️ TASK INVALID] user={user_id}, task_id={task_id}")
                await callback.answer("❌ تسک پیدا نشد یا قبلاً انجام شده.", show_alert=True)
                return

            logger.info(f"[✅ TASK MARKED DONE] user={user_id}, task_id={task.id}")
            await callback.answer("✅ تسک با موفقیت انجام شد!")

            # ✏️ ویرایش پیام اصلی
            updated_text = (
                f"✅ <b>{task.content}</b>\n"
                f"⏰ {task.due_date.strftime('%Y-%m-%d') if task.due_date else 'بدون سررسید'} | ✅ انجام شده"
            )

            try:
                await callback.message.edit_text(updated_text)
            except Exception as edit_err:
                logger.warning(f"[⚠️ EDIT FAILED] task_id={task_id}, error={edit_err}")

    except Exception as e:
        logger.exception(f"[💥 ERROR] handle_mark_task_done user_id={user_id} -> {e}")
        await callback.answer("⚠️ خطایی رخ داد. لطفاً مجدداً تلاش کن.", show_alert=True)


# ─────────────────────────────────────────────
# 🔧 استخراج task_id از callback_data
# ─────────────────────────────────────────────
def extract_task_id(callback_data: str) -> int | None:
    try:
        return int(callback_data.split(":")[1])
    except (IndexError, ValueError):
        return None
