# core/handlers/start.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from bot.keyboards.main_menu import main_menu_keyboard
from database.session import get_session
from database.crud import create_or_update_user
from core.config import get_settings
import database.crud as crud
import logging

router = Router()
logger = logging.getLogger(__name__)
settings = get_settings()

@router.message(CommandStart())
async def handle_start(message: Message):
    user = message.from_user
    logger.info(f"[👋 /start] {user.full_name} ({user.id}) started the bot.")

    try:
        async with get_session() as session:
            await crud.create_or_update_user(
                session=session,
                telegram_id=user.id,
                full_name=user.full_name,
                username=user.username,
                language=user.language_code or settings.DEFAULT_LANG,
            )

        await message.answer(
            "<b>🎉 به DoTask خوش‌اومدی!</b>\n\n"
            "من اینجام تا کمکت کنم تسک‌هاتو مدیریت کنی. 🧠\n\n"
            "➕ تسک اضافه کن\n"
            "📋 لیست تسک‌هاتو ببین\n"
            "👇 یکی از گزینه‌های زیر رو انتخاب کن:",
            reply_markup=main_menu_keyboard(),
        )

    except Exception as e:
        logger.exception(f"[💥 START FAILED] user={user.id} -> {e}")
        await message.answer("❌ خطا در اجرای ربات. لطفاً بعداً امتحان کن.")
