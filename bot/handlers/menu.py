from aiogram import Router, F
from aiogram.types import Message
import logging

from bot.keyboards.main_menu import main_menu_keyboard
from database.session import get_session
from database.crud import get_user_by_telegram_id, get_tasks_by_user_id

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "📋 لیست وظایف")
async def handle_list_tasks(message: Message):
    user_id = message.from_user.id
    logger.info(f"[📋 LIST_TASKS] User {user_id} درخواست لیست تسک کرد.")

    try:
        async with get_session() as session:
            db_user = await get_user_by_telegram_id(session, telegram_id=user_id)

            if not db_user:
                logger.warning(f"[❌ USER NOT FOUND] telegram_id={user_id}")
                await message.answer("❗ کاربر شناسایی نشد. لطفاً /start رو بزن.")
                return

            tasks = await get_tasks_by_user_id(session, user_id=db_user.id)

            if not tasks:
                await message.answer("📭 هنوز هیچ تسکی ثبت نکردی.", reply_markup=main_menu_keyboard())
                return

            lines = []
            for i, task in enumerate(tasks, start=1):
                due = f"⏰ {task.due_date.date()}" if task.due_date else "⏱ بدون تاریخ"
                status = "✅ انجام شده" if task.is_done else "⏳ در انتظار"
                lines.append(f"{i}. {task.content}\n{due} | {status}\n")

            response = "📝 <b>لیست وظایف ثبت‌شده:</b>\n\n" + "\n".join(lines)
            await message.answer(response, reply_markup=main_menu_keyboard())

    except Exception as e:
        logger.exception(f"[💥 ERROR @ list_tasks] User {user_id} -> {e}")
        await message.answer("⚠️ خطای غیرمنتظره‌ای رخ داد. لطفاً دوباره امتحان کن.")
