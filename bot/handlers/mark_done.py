# bot/handlers/mark_done.py

from aiogram import Router
from aiogram.types import CallbackQuery
from database.session import get_session
from database.crud import get_user_by_telegram_id, mark_task_as_done
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data and c.data.startswith("done:"))
async def handle_mark_task_done(callback: CallbackQuery):
    user_id = callback.from_user.id
    callback_data = callback.data

    try:
        raw_task_id = callback_data.split(":")[1]

        if not raw_task_id.isdigit():
            await callback.answer("❗ شناسه تسک نامعتبر است.", show_alert=True)
            return

        task_id = int(raw_task_id)

        async with get_session() as session:
            db_user = await get_user_by_telegram_id(session, telegram_id=user_id)

            if not db_user:
                logger.warning(f"[❌ USER NOT FOUND] telegram_id={user_id}")
                await callback.answer("❗ کاربر شناسایی نشد. ابتدا /start را بزن.", show_alert=True)
                return

            task = await mark_task_as_done(session, user_id=db_user.id, task_id=task_id)

            if not task:
                logger.warning(f"[❌ TASK NOT FOUND or already done] task_id={task_id}")
                await callback.answer("❌ تسک پیدا نشد یا قبلاً انجام شده.", show_alert=True)
                return

            logger.info(f"[✅ TASK DONE] user={user_id} -> task_id={task.id}")

            await callback.answer("✅ تسک با موفقیت انجام شد!")
            await callback.message.edit_text(
                f"✅ <b>{task.content}</b>\n"
                f"⏰ {task.due_date.date() if task.due_date else 'بدون سررسید'} | ✅ انجام شده"
            )

    except Exception as e:
        logger.exception(f"[💥 ERROR @ handle_mark_task_done] user={user_id} -> {e}")
        await callback.answer("⚠️ خطایی پیش آمد. لطفاً دوباره امتحان کن.", show_alert=True)
