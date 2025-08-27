from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.main_menu import main_menu_keyboard
from database.session import get_session
from database.crud import get_tasks_by_user_id, create_or_update_user

import logging

router = Router()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# ✅ اطمینان از وجود کاربر در دیتابیس
# ─────────────────────────────────────────────
async def ensure_user_exists(session, user_data) -> int | None:
    try:
        user = await create_or_update_user(
            session=session,
            telegram_id=user_data.id,
            full_name=user_data.full_name,
            username=user_data.username,
            language=user_data.language_code or "fa"
        )
        if not user:
            logger.warning(f"[❗ USER NOT FOUND] telegram_id={user_data.id}")
        return user.id if user else None
    except Exception as e:
        logger.exception(f"[💥 USER GET/CREATE ERROR] user_id={user_data.id} -> {e}")
        return None


# ─────────────────────────────────────────────
# 🎛️ ساخت کیبورد تسک (انجام / حذف)
# ─────────────────────────────────────────────
def get_task_inline_keyboard(task_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ انجام شد", callback_data=f"done:{task_id}"),
        InlineKeyboardButton(text="🗑 حذف", callback_data=f"delete:{task_id}")
    )
    return builder.as_markup()


# ─────────────────────────────────────────────
# 📋 نمایش لیست تسک‌ها به کاربر
# ─────────────────────────────────────────────
@router.message(F.text == "📋 لیست وظایف")
async def handle_list_tasks(message: Message) -> None:
    user_info = message.from_user
    logger.info(f"[📋 LIST TASKS REQUESTED] user_id={user_info.id}")

    async with get_session() as session:
        try:
            user_id = await ensure_user_exists(session, user_info)

            if not user_id:
                await message.answer("❗ حساب شما شناسایی نشد. لطفاً /start را بزنید.")
                return

            tasks = await get_tasks_by_user_id(session, user_id=user_id)

            if not tasks:
                await message.answer("📭 هنوز هیچ تسکی ثبت نکردی.", reply_markup=main_menu_keyboard())
                return

            for idx, task in enumerate(tasks, start=1):
                await _send_task_to_user(message, task, idx)

            await message.answer("🔙 برگشت به منوی اصلی:", reply_markup=main_menu_keyboard())

        except Exception as e:
            logger.exception(f"[💥 ERROR @ handle_list_tasks] user_id={user_info.id} -> {e}")
            await message.answer("⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.", reply_markup=main_menu_keyboard())


# ─────────────────────────────────────────────
# 🧠 ارسال تسک به صورت جداگانه به کاربر
# ─────────────────────────────────────────────
async def _send_task_to_user(message: Message, task, index: int) -> None:
    try:
        due_text = f"⏰ {task.due_date.strftime('%Y-%m-%d')}" if task.due_date else "🕓 بدون تاریخ"
    except Exception as e:
        due_text = "🕓 تاریخ نامعتبر"
        logger.warning(f"[⚠️ INVALID DATE FORMAT] task_id={task.id} -> {e}")

    status_text = "✅ انجام شده" if task.is_done else "🕒 در انتظار"
    content = task.content or "❓ بدون عنوان"

    text = (
        f"<b>{index}.</b> {content}\n"
        f"{due_text} | {status_text}"
    )

    markup = get_task_inline_keyboard(task.id) if not task.is_done else None

    try:
        await message.answer(text, reply_markup=markup)
        logger.debug(f"[📄 TASK SENT] task_id={task.id}, user_id={message.from_user.id}")
    except Exception as e:
        logger.warning(f"[⚠️ FAILED TO SEND TASK] task_id={task.id} -> {e}")
