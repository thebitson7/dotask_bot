# core/startup.py
from __future__ import annotations

import asyncio
import inspect
import logging
import signal
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from typing import Any, Tuple

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.strategy import FSMStrategy
from aiogram.fsm.storage.memory import MemoryStorage

# Redis (اختیاری)
try:
    import redis.asyncio as aioredis  # type: ignore
    from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
except Exception:  # pragma: no cover
    aioredis = None
    RedisStorage = None  # type: ignore

from core.config import get_settings
from database.session import init_db

# Routers
logger = logging.getLogger("DoTaskStartup")
try:
    from bot.handlers import add_task, delete_task, mark_done, menu, list_tasks
    from bot.handlers import start as start_handler
except Exception as e:
    logger.exception("❌ Router import failed: %s", e)
    raise

# Webhook server (aiohttp) - فقط وقتی WEBHOOK_MODE=True
try:
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
except Exception:  # pragma: no cover
    web = None  # type: ignore

settings = get_settings()


async def _resolve_storage() -> Any:
    """
    انتخاب بهترین ذخیره‌ساز FSM:
    - RedisStorage اگر REDIS_URL تنظیم شده و وابستگی‌ها موجود باشند.
    - در غیر اینصورت MemoryStorage.
    """
    if settings.REDIS_URL and aioredis and RedisStorage:
        try:
            redis = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
            with suppress(Exception):
                await redis.ping()
            logger.info("🔌 Using Redis storage for FSM")
            return RedisStorage(
                redis=redis,
                key_builder=DefaultKeyBuilder(with_bot_id=True),
            )
        except Exception as e:
            logger.warning("⚠️ Redis unavailable (%s). Falling back to MemoryStorage.", e)

    logger.info("💾 Using in-memory FSM storage")
    return MemoryStorage()


def _include_routers(dp: Dispatcher) -> None:
    """
    ثبت همه‌ی روترها در یک نقطه.
    ترتیب مهم است: /start قبل از بقیه.
    """
    dp.include_routers(
        start_handler.router,
        add_task.router,
        mark_done.router,
        delete_task.router,
        list_tasks.router,  # نمایش/فیلتر/صفحه‌بندی تسک‌ها
        menu.router,
    )
    logger.debug("🧭 Routers registered: start, add_task, mark_done, delete_task, list_tasks, menu")


async def _maybe_setup_bot_commands(bot: Bot) -> None:
    """
    اگر bot/commands.py فانکشن setup داشته باشد، دستورات بات را ثبت می‌کند.
    """
    with suppress(Exception):
        import importlib

        mod = importlib.import_module("bot.commands")
        for name in ("setup", "setup_bot_commands", "register", "set_bot_commands"):
            fn = getattr(mod, name, None)
            if fn:
                if inspect.iscoroutinefunction(fn):
                    await fn(bot)
                else:
                    fn(bot)
                logger.info("✅ Bot commands registered via bot.commands.%s()", name)
                return


async def _startup_common() -> Tuple[Bot, Dispatcher]:
    """
    کارهای مشترک استارتاپ:
    - init DB
    - ساخت Bot و Dispatcher
    - اعتبارسنجی توکن با get_me (لاگ واضح)
    - ثبت روترها
    - ثبت دستورات بات (اختیاری)
    """
    logger.info("📦 Initializing database...")
    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # اعتبارسنجی توکن/اتصال همین ابتدا تا اگر ایرادی هست زود بترکد
    try:
        me = await bot.get_me()
        logger.info("🤖 Bot authorized: @%s (id=%s)", me.username, me.id)
    except Exception as e:
        logger.critical("🚫 Telegram authorization failed: %s", e, exc_info=True)
        with suppress(Exception):
            await bot.session.close()
        raise

    storage = await _resolve_storage()
    dp = Dispatcher(
        storage=storage,
        fsm_strategy=FSMStrategy.CHAT,
    )

    _include_routers(dp)
    await _maybe_setup_bot_commands(bot)

    return bot, dp


async def _run_polling(bot: Bot, dp: Dispatcher) -> None:
    """
    شروع Long Polling با تنظیمات امن.
    """
    logger.info("🔁 Starting in Long Polling mode…")

    # اطمینان از اینکه وبهوک قبلی حذف شده و آپدیت‌های قدیمی نمی‌آیند
    with suppress(Exception):
        await bot.delete_webhook(drop_pending_updates=True)

    # اگر Aiogram توانست تشخیص دهد، همان؛ وگرنه صریح تعیین می‌کنیم
    try:
        allowed_updates = dp.resolve_used_update_types()
        if not allowed_updates:
            raise ValueError("empty")
    except Exception:
        allowed_updates = ["message", "callback_query"]

    logger.debug("Allowed updates: %s", allowed_updates)

    await dp.start_polling(
        bot,
        allowed_updates=allowed_updates,
    )


async def _run_webhook(bot: Bot, dp: Dispatcher) -> None:
    """
    راه‌اندازی وبهوک با aiohttp (مخصوص Production).
    """
    if web is None:
        raise RuntimeError("aiohttp is not available. Install it or disable WEBHOOK_MODE.")

    if not settings.webhook_url:
        raise ValueError("WEBHOOK_MODE=True but webhook_url is not configured properly.")

    logger.info("🌐 Starting in Webhook mode at %s", settings.webhook_url)

    app = web.Application()

    # ثبت هندلر وبهوک Aiogram
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.WEBHOOK_SECRET,
    )
    webhook_handler.register(app, path=settings.WEBHOOK_PATH)

    # هوک‌های استارتاپ/شات‌داون دیسپچر
    setup_application(app, dp, bot=bot)

    # تنظیم وبهوک سمت تلگرام
    await bot.set_webhook(
        url=settings.webhook_url,
        secret_token=settings.WEBHOOK_SECRET,
        drop_pending_updates=True,
    )

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.HOST, settings.PORT)
    await site.start()
    logger.info("🚀 Webhook server listening on %s:%d", settings.HOST, settings.PORT)

    # اجرای دائمی تا زمان لغو
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        with suppress(Exception):
            await runner.cleanup()


@asynccontextmanager
async def _lifespan(bot: Bot, dp: Dispatcher):
    """
    مدیریت شات‌داون تمیز (SIGINT/SIGTERM).
    روی ویندوز ممکن است سیگنال‌ها محدود باشند، suppress شده‌اند.
    """
    loop = asyncio.get_running_loop()

    def _stop_signal(signame: str):
        logger.warning("🛑 Received %s -> shutting down…", signame)

    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _stop_signal, sig.name)

    try:
        yield
    finally:
        logger.info("🔻 Closing bot & storage…")
        with suppress(Exception):
            await dp.storage.close()
        with suppress(Exception):
            await bot.session.close()


async def start_bot() -> None:
    """
    ورودی اصلی اپ. بات را در حالت Polling یا Webhook بالا می‌آورد.
    """
    bot, dp = await _startup_common()
    logger.info("✅ Bot is ready to receive updates.")

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(_lifespan(bot, dp))

        try:
            if settings.WEBHOOK_MODE:
                await _run_webhook(bot, dp)
            else:
                await _run_polling(bot, dp)
        except asyncio.CancelledError:  # pragma: no cover
            logger.info("Cancelled, exiting…")
        except Exception as e:
            logger.critical("🔥 BOT CRASHED: %s", e, exc_info=True)
            raise
