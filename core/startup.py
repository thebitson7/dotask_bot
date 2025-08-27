# core/startup.py

import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.strategy import FSMStrategy
from aiogram.fsm.storage.memory import MemoryStorage

from core.config import get_settings
from database.session import init_db
from bot.handlers import add_task, mark_done, delete_task, menu
from bot.handlers import start as start_handler  # 👈 فایل جدید هندلر استارت

logger = logging.getLogger("DoTaskStartup")
settings = get_settings()


async def start_bot():
    logger.info("📦 آماده‌سازی دیتابیس...")
    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(
        storage=MemoryStorage(),
        fsm_strategy=FSMStrategy.CHAT
    )

    dp.include_routers(
        start_handler.router,     # 👈 هندلر استارت
        add_task.router,
        mark_done.router,
        delete_task.router,
        menu.router,
    )

    logger.info("✅ ربات آماده دریافت پیام است...")

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"[🔥 BOT CRASHED] -> {e}")
