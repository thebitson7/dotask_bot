# bot/handlers/menu.py

from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from bot.keyboards.main_menu import main_menu_keyboard
from database.session import get_session
from database.crud import get_user_by_telegram_id, get_tasks_by_user_id

import logging

router = Router()
logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────
# 🎛 ساخت دکمه «انجام شد» برای تسک
# ───────────────────────────────────────────────
def get_task_inline_keyboard(task_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ انجام شد",
        callback_data=f"done:{task_id}"
    )
    return builder.as_markup()


# ───────────────────────────────────────────────
# 📋 نمایش لیست تسک‌ها
# ───────────────────────────────────────────────
@router.message(F.text == "📋 لیست وظایف")
async def handle_list_tasks(message: Message):
    user_id = message.from_user.id
    logger.info(f"[📋 LIST_TASKS] User {user_id} requested their task list.")

    try:
        async with get_session() as session:
            user = await get_user_by_telegram_id(session, telegram_id=user_id)

            if not user:
                logger.warning(f"[❌ USER NOT FOUND] telegram_id={user_id}")
                await message.answer("❗ حساب شما پیدا نشد. لطفاً /start را بزن.")
                return

            tasks = await get_tasks_by_user_id(session, user_id=user.id)

            if not tasks:
                await message.answer("📭 هنوز هیچ تسکی ثبت نکردی.", reply_markup=main_menu_keyboard())
                return

            for idx, task in enumerate(tasks, start=1):
                due_text = f"⏰ {task.due_date.date()}" if task.due_date else "🕓 بدون تاریخ"
                status_text = "✅ انجام شده" if task.is_done else "🕒 در انتظار"

                message_text = (
                    f"<b>{idx}.</b> {task.content}\n"
                    f"{due_text} | {status_text}"
                )

                reply_markup = None
                if not task.is_done:
                    reply_markup = get_task_inline_keyboard(task.id)

                await message.answer(message_text, reply_markup=reply_markup)

            await message.answer("🔙 برگشت به منوی اصلی:", reply_markup=main_menu_keyboard())

    except Exception as e:
        logger.exception(f"[💥 ERROR @ handle_list_tasks] user={user_id} -> {e}")
        await message.answer("⚠️ خطایی رخ داد. لطفاً دوباره امتحان کن.", reply_markup=main_menu_keyboard())
