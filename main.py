# main.py

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.strategy import FSMStrategy
from aiogram.filters import CommandStart
from aiogram.types import Message

from core.config import get_settings
from database.session import init_db, get_session
from database import crud

from bot.keyboards.main_menu import main_menu_keyboard
from bot.handlers import (
    add_task,
    mark_done,
    menu,
)

# ─────────────────────────────────────────────
# 🔧 لاگ مرکزی پروژه
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("DoTask")
settings = get_settings()


# ─────────────────────────────────────────────
# 🚀 تابع اصلی اجرا
# ─────────────────────────────────────────────
async def main() -> None:
    logger.info("🔄 Initializing database...")
    await init_db()

    logger.info("🤖 Starting bot instance...")
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher(
        storage=MemoryStorage(),
        fsm_strategy=FSMStrategy.CHAT
    )

    # ───────────── ثبت روترها ─────────────
    dp.include_router(add_task.router)
    dp.include_router(mark_done.router)
    dp.include_router(menu.router)

    # ─────────────────────────────────────────
    # 👋 هندل فرمان /start
    # ─────────────────────────────────────────
    @dp.message(CommandStart())
    async def handle_start(message: Message) -> None:
        from_user = message.from_user
        logger.info(f"[👋 START] {from_user.full_name} ({from_user.id}) وارد شد.")

        async with get_session() as session:
            await crud.create_or_update_user(
                session=session,
                telegram_id=from_user.id,
                full_name=from_user.full_name,
                username=from_user.username,
                language=from_user.language_code or settings.DEFAULT_LANG,
            )

        await message.answer(
            "<b>🎉 خوش اومدی به DoTask!</b>\n\n"
            "من اینجام تا کمکت کنم تسک‌هات رو حرفه‌ای مدیریت کنی.\n"
            "با من می‌تونی:\n"
            "➕ تسک جدید بسازی\n"
            "📋 لیست وظایف‌ت رو ببینی\n"
            "⚙️ تنظیمات رو تغییر بدی\n\n"
            "👇 یکی از گزینه‌های زیر رو انتخاب کن:",
            reply_markup=main_menu_keyboard()
        )

    logger.info("📡 Polling started...")
    await dp.start_polling(bot)


# ─────────────────────────────────────────────
# ⏹️ اجرای مستقیم فایل
# ─────────────────────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.warning("⛔ Bot stopped manually.")
