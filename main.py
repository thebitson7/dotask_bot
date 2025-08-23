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
from database.db import init_db, get_session
from database import crud

from bot.keyboards.main_menu import main_menu_keyboard
from bot.handlers import add_task, menu  # ⚠️ ترتیب مهم است

# ───────────────────────────────────────
# 📌 Logging Configuration
# ───────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("Dotask")
settings = get_settings()

# ───────────────────────────────────────
# 🚀 Bot Entry Point
# ───────────────────────────────────────
async def main() -> None:
    logger.info("🔧 Initializing database...")
    await init_db()

    logger.info("🤖 Creating bot instance...")
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher(
        storage=MemoryStorage(),
        fsm_strategy=FSMStrategy.CHAT
    )

    logger.info("🧩 Registering routers...")
    dp.include_router(add_task.router)  # اول منطق تسک
    dp.include_router(menu.router)      # بعد منوی اصلی

    # ─────────────────────────────────────
    # 👋 /start command handler
    # ─────────────────────────────────────
    @dp.message(CommandStart())
    async def handle_start(message: Message) -> None:
        from_user = message.from_user
        logger.info(f"📥 New /start from {from_user.full_name} ({from_user.id})")

        async with get_session() as session:
            await crud.create_or_update_user(
                session=session,
                telegram_id=from_user.id,
                full_name=from_user.full_name,
                username=from_user.username,
                language=from_user.language_code or "fa"
            )

        await message.answer(
            "<b>🎉 خوش اومدی به Dotask!</b>\n\n"
            "من اینجام تا کمکت کنم تسک‌هات رو راحت‌تر مدیریت کنی. ✨\n\n"
            "با استفاده از من می‌تونی:\n"
            "✅ تسک جدید اضافه کنی\n"
            "📋 لیست وظایف‌ت رو ببینی\n"
            "⚙️ تنظیمات رو تغییر بدی\n\n"
            "👇 یکی از گزینه‌های منو رو انتخاب کن:",
            reply_markup=main_menu_keyboard()
        )

    logger.info("📡 Starting polling...")
    await dp.start_polling(bot)

# ───────────────────────────────────────
# ⏹️ Run the bot
# ───────────────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.warning("⛔ Bot stopped manually.")
