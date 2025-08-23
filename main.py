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
from bot.handlers import add_task, menu  # ⚠️ add_task باید قبل از menu وارد و ثبت بشه

# لاگ برای دیباگ
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)
settings = get_settings()


async def main():
    logger.info("🧠 Initializing database...")
    await init_db()

    logger.info("⚙️ Creating bot and dispatcher...")
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage, fsm_strategy=FSMStrategy.CHAT)

    logger.info("📌 Registering routers...")
    
    dp.include_router(add_task.router)  # ✅ اول این
    dp.include_router(menu.router)      # ✅ بعد این


    # دستور /start
    @dp.message(CommandStart())
    async def handle_start(message: Message):
        from_user = message.from_user

        async with get_session() as session:
            await crud.create_or_update_user(
                session=session,
                telegram_id=from_user.id,
                full_name=from_user.full_name,
                username=from_user.username,
                language=from_user.language_code or "fa",
            )

        await message.answer(
                "<b>🎉 خوش اومدی به Dotask!</b>\n\n"
                "من اینجام تا کمکت کنم تسک‌هات رو راحت‌تر مدیریت کنی. ✨\n"
                "با استفاده از من می‌تونی:\n"
                "➕ تسک جدید اضافه کنی\n"
                "📋 تسک‌های قبلی رو ببینی و پیگیری کنی\n"
                "⚙️ تنظیمات رو تغییر بدی\n\n"
                "👇 از منوی پایین یکی از گزینه‌ها رو انتخاب کن و شروع کن...",
                reply_markup=main_menu_keyboard()
            )


    logger.info("🚀 Starting Dotask Bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.warning("⛔ Bot stopped.")
