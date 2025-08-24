# main.py

import asyncio
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
from bot.handlers import (
    add_task,
    mark_done,
    delete_task,  # ⬅️ اضافه‌شده برای حذف تسک
    menu,
)

# ─────────────────────────────────────────────
# 🔧 Logging Configuration
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if get_settings().ENV == "development" else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("DoTask")
settings = get_settings()


# ─────────────────────────────────────────────
# 🚀 Main Bot Entry Point
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

    # ──────────────────────────────
    # 🔌 Register all routers
    # ──────────────────────────────
    dp.include_routers(
        add_task.router,
        mark_done.router,
        delete_task.router,  # ✅ حذف تسک
        menu.router
    )

    # ──────────────────────────────
    # 👋 Handle /start command
    # ──────────────────────────────
    @dp.message(CommandStart())
    async def handle_start(message: Message) -> None:
        from_user = message.from_user
        logger.info(f"[👋 START] {from_user.full_name} ({from_user.id}) started bot.")

        async with get_session() as session:
            await crud.create_or_update_user(
                session=session,
                telegram_id=from_user.id,
                full_name=from_user.full_name,
                username=from_user.username,
                language=from_user.language_code or settings.DEFAULT_LANG,
            )

        await message.answer(
            "<b>🎉 Welcome to DoTask!</b>\n\n"
            "I’m here to help you manage your tasks like a pro! 🧠\n\n"
            "You can:\n"
            "➕ Add new tasks\n"
            "📋 View your to-dos\n"
            "⚙️ Adjust settings\n\n"
            "👇 Select an option below:",
            reply_markup=main_menu_keyboard()
        )

    logger.info("📡 Polling started. Bot is now running...")
    await dp.start_polling(bot)


# ─────────────────────────────────────────────
# ⏹️ Run bot when script is executed directly
# ─────────────────────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.warning("🛑 Bot stopped manually.")
