import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.strategy import FSMStrategy
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart
from aiogram.types import Message

from core.config import get_settings
from database.session import init_db, get_session
from database import crud

from bot.keyboards.main_menu import main_menu_keyboard
from bot.handlers import add_task, mark_done, delete_task, menu

logger = logging.getLogger("DoTaskStartup")
settings = get_settings()


# ─────────────────────────────────────────────
# 👋 هندلر /start (ورودی به ربات)
# ─────────────────────────────────────────────
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
            "من اینجام تا بهت کمک کنم تسک‌هات رو مدیریت کنی. 🧠\n\n"
            "تو می‌تونی:\n"
            "➕ تسک جدید اضافه کنی\n"
            "📋 لیست تسک‌هاتو ببینی\n"
            "⚙️ تنظیماتت رو تغییر بدی\n\n"
            "👇 یکی از گزینه‌های زیر رو انتخاب کن:",
            reply_markup=main_menu_keyboard(),
        )

    except Exception as e:
        logger.exception(f"[💥 START FAILED] user={user.id} -> {e}")
        await message.answer("❌ خطا در اجرای ربات. لطفاً بعداً دوباره تلاش کن.")


# ─────────────────────────────────────────────
# 🚀 راه‌اندازی ربات
# ─────────────────────────────────────────────
async def start_bot():
    logger.info("📦 در حال آماده‌سازی دیتابیس...")
    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(
        storage=MemoryStorage(),
        fsm_strategy=FSMStrategy.CHAT
    )

    # ✅ ثبت هندلر /start
    dp.message.register(handle_start, CommandStart())

    # ✅ ثبت سایر هندلرها
    dp.include_routers(
        add_task.router,
        mark_done.router,
        delete_task.router,
        menu.router,
    )

    logger.info("✅ ربات با موفقیت راه‌اندازی شد. در حال دریافت پیام‌ها...")

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"[🔥 BOT CRASHED] -> {e}")
