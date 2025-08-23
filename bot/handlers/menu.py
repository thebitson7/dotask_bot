# bot/handlers/menu.py

from aiogram import Router, F
from aiogram.types import Message
import logging

from bot.keyboards.main_menu import main_menu_keyboard
from database.session import get_session
from database.crud import get_user_by_telegram_id, get_tasks_by_user_id

router = Router()
logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────
# 📋 نمایش لیست تسک‌های کاربر
# ───────────────────────────────────────────────
@router.message(F.text == "📋 لیست وظایف")
async def handle_list_tasks(message: Message):
    user_id = message.from_user.id
    logger.info(f"[📋 LIST_TASKS] User {user_id} درخواست لیست تسک داد.")

    try:
        async with get_session() as session:
            user = await get_user_by_telegram_id(session, telegram_id=user_id)

            if not user:
                logger.warning(f"[❌ USER NOT FOUND] telegram_id={user_id}")
                await message.answer("❗ حساب شما شناسایی نشد. لطفاً ابتدا /start را بزنید.")
                return

            tasks = await get_tasks_by_user_id(session, user_id=user.id)

            if not tasks:
                await message.answer("📭 هنوز هیچ تسکی ثبت نکردی.", reply_markup=main_menu_keyboard())
                return

            # ساختن لیست نمایشی
            lines = []
            for i, task in enumerate(tasks, start=1):
                due = f"⏰ {task.due_date.date()}" if task.due_date else "🕓 بدون تاریخ"
                status = "✅ انجام شده" if task.is_done else "🕒 در انتظار"
                lines.append(f"<b>{i}.</b> {task.content}\n{due} | {status}\n")

            response = (
                f"📝 <b>لیست وظایف شما ({len(tasks)} تسک):</b>\n\n" +
                "\n".join(lines)
            )

            await message.answer(response, reply_markup=main_menu_keyboard())

    except Exception as e:
        logger.exception(f"[💥 ERROR] handle_list_tasks for user={user_id}: {e}")
        await message.answer("⚠️ متأسفم، مشکلی در دریافت تسک‌ها پیش آمد. لطفاً دوباره امتحان کن.", reply_markup=main_menu_keyboard())


# ───────────────────────────────────────────────
# ⚙️ تنظیمات (در حال توسعه)
# ───────────────────────────────────────────────
@router.message(F.text == "⚙️ تنظیمات")
async def handle_settings(message: Message):
    logger.info(f"[⚙️ SETTINGS] User {message.from_user.id} وارد تنظیمات شد.")
    await message.answer("🛠 بخش تنظیمات در دست توسعه است. به‌زودی در دسترس خواهد بود.")


# ───────────────────────────────────────────────
# ℹ️ راهنما / Help
# ───────────────────────────────────────────────
@router.message(F.text == "ℹ️ راهنمای استفاده")
async def handle_help(message: Message):
    logger.info(f"[ℹ️ HELP] User {message.from_user.id} درخواست راهنما داد.")
    await message.answer(
        "📘 <b>راهنمای استفاده از Dotask Bot</b>\n\n"
        "➕ <b>افزودن تسک:</b> یک وظیفه جدید به لیست اضافه کن.\n"
        "📋 <b>لیست وظایف:</b> ببین چه کارهایی ثبت کردی و چه کارهایی مونده.\n"
        "⚙️ <b>تنظیمات:</b> در آینده امکان تغییرات شخصی فراهم میشه.\n"
        "ℹ️ <b>راهنما:</b> همین پیامه 😄\n\n"
        "🔄 برای برگشت به منوی اصلی از /start یا دکمه‌ها استفاده کن.",
        reply_markup=main_menu_keyboard()
    )
