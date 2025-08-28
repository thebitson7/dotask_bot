# bot/handlers/start.py
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest

from bot.keyboards.main_menu import main_menu_keyboard
from database.session import get_session
from database.crud import create_or_update_user
from core.config import get_settings
import logging

router = Router()
logger = logging.getLogger(__name__)
settings = get_settings()

@router.message(CommandStart())
async def handle_start(message: Message):
    user = message.from_user
    logger.info(f"[👋 /start] {user.full_name} ({user.id})")

    # 1) ایجاد/به‌روزرسانی کاربر با لاگ شفاف
    try:
        logger.debug("[/start] ensure user in DB...")
        async with get_session() as session:
            _ = await create_or_update_user(
                session=session,
                telegram_id=user.id,
                full_name=user.full_name,
                username=user.username,
                language=(user.language_code or settings.DEFAULT_LANG),
            )
        logger.debug("[/start] ensure user DONE.")
    except Exception as e:
        # اگر اینجا خطا خورد هم هنوز می‌خواهیم پیام خوش‌آمد بدهیم
        logger.exception(f"[/start] ensure_user failed (tg={user.id}) -> {e}")

    # 2) ساخت کیبورد با محافظ
    kb = None
    try:
        logger.debug("[/start] build main menu keyboard...")
        kb = main_menu_keyboard()
        logger.debug("[/start] keyboard OK.")
    except Exception as e:
        logger.exception(f"[/start] main_menu_keyboard() failed -> {e}")
        kb = None  # بدون کیبورد ادامه بده

    # 3) ارسال پیام خوش‌آمد (HTML ساده، بدون وابستگی به parse_mode)
    welcome = (
        "<b>🎉 به DoTask خوش اومدی!</b>\n\n"
        "من اینجام که کمکت کنم تسک‌هات رو مدیریت کنی. 🧠\n\n"
        "➕ تسک اضافه کن\n"
        "📋 لیست تسک‌هات رو ببین\n"
        "👇 یکی از گزینه‌های زیر رو انتخاب کن:"
    )

    try:
        await message.answer(welcome, reply_markup=kb)
        logger.info("[/start] welcome message sent.")
    except TelegramBadRequest as e:
        logger.exception(f"[/start] TelegramBadRequest sending welcome -> {e}")
        # نسخه‌ی امن‌تر پیام، بدون HTML و بدون کیبورد
        try:
            await message.answer(
                "🎉 به DoTask خوش اومدی!\n\n"
                "➕ تسک اضافه کن\n"
                "📋 لیست تسک‌ها رو ببین"
            )
        except Exception as e2:
            logger.exception(f"[/start] fallback send failed -> {e2}")
            await message.answer("❌ خطا در اجرای ربات. لطفاً بعداً تلاش کن.")
    except Exception as e:
        logger.exception(f"[/start] unexpected error sending welcome -> {e}")
        await message.answer("❌ خطا در اجرای ربات. لطفاً بعداً تلاش کن.")
