# core/startup.py
from __future__ import annotations

import asyncio
import inspect
import logging
import signal
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from typing import Any, Optional, Tuple

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.strategy import FSMStrategy
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import BaseStorage

# Redis (اختیاری)
try:
    import redis.asyncio as aioredis  # type: ignore
    from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
except Exception:  # pragma: no cover
    aioredis = None
    RedisStorage = None  # type: ignore

from core.config import get_settings
from database.session import init_db, shutdown_db

logger = logging.getLogger("DoTaskStartup")

# روترها (اول /start)
try:
    from bot.handlers import add_task, delete_task, mark_done, menu, list_tasks
    from bot.handlers import start as start_handler
except Exception as e:
    logger.exception("❌ Router import failed: %s", e)
    raise

# Webhook server (aiohttp) - وقتی WEBHOOK_MODE=True
try:
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
except Exception:  # pragma: no cover
    web = None  # type: ignore

settings = get_settings()

# ─────────────────────────────────────────────────────────
# 🧩 Sentry (اختیاری)
# ─────────────────────────────────────────────────────────
def _maybe_setup_sentry() -> None:
    if not settings.SENTRY_DSN:
        return
    import importlib
    try:
        sentry_sdk = importlib.import_module("sentry_sdk")
    except ModuleNotFoundError:
        logger.warning("⚠️ sentry-sdk not installed. Unset SENTRY_DSN or `pip install sentry-sdk`.")
        return

    integrations = []
    # Logging integration (اختیاری)
    try:
        LoggingIntegration = importlib.import_module(
            "sentry_sdk.integrations.logging"
        ).LoggingIntegration
        integrations.append(LoggingIntegration(level=logging.INFO, event_level=logging.ERROR))
    except Exception:
        pass

    # aiohttp integration (اختیاری)
    try:
        AioHttpIntegration = importlib.import_module(
            "sentry_sdk.integrations.aiohttp"
        ).AioHttpIntegration
        integrations.append(AioHttpIntegration())
    except Exception:
        pass

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=integrations,
        traces_sample_rate=0.0,
        profiles_sample_rate=0.0,
        environment=settings.ENV,
    )
    names = ", ".join(type(i).__name__ for i in integrations) or "no-integrations"
    logger.info("🪪 Sentry initialized (%s)", names)


# ─────────────────────────────────────────────────────────
# 💾 Storage: Redis یا Memory
# ─────────────────────────────────────────────────────────
async def _resolve_storage() -> Tuple[BaseStorage, Optional[Any]]:
    """
    RedisStorage اگر REDIS_URL و وابستگی‌ها OK باشند، وگرنه MemoryStorage.
    خروجی: (storage, redis_client_or_none)
    """
    if settings.REDIS_URL and aioredis and RedisStorage:
        try:
            redis = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
            with suppress(Exception):
                await redis.ping()
            logger.info("🔌 Using Redis storage for FSM")
            storage = RedisStorage(redis=redis, key_builder=DefaultKeyBuilder(with_bot_id=True))
            return storage, redis
        except Exception as e:
            logger.warning("⚠️ Redis unavailable (%s). Falling back to MemoryStorage.", e)

    logger.info("💾 Using in-memory FSM storage")
    return MemoryStorage(), None


# ─────────────────────────────────────────────────────────
# 🧭 ثبت روترها
# ─────────────────────────────────────────────────────────
def _include_routers(dp: Dispatcher) -> None:
    dp.include_routers(
        start_handler.router,   # همیشه اول
        add_task.router,
        mark_done.router,
        delete_task.router,
        list_tasks.router,
        menu.router,
    )
    logger.debug("🧭 Routers registered: start, add_task, mark_done, delete_task, list_tasks, menu")


# ─────────────────────────────────────────────────────────
# 🧾 Bot commands (اختیاری)
# ─────────────────────────────────────────────────────────
async def _maybe_setup_bot_commands(bot: Bot) -> None:
    """
    اگر bot/commands.py فانکشنی مانند setup|setup_bot_commands|register داشت، دستورات را ثبت می‌کند.
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


# ─────────────────────────────────────────────────────────
# 🚀 مرحله مشترک استارت
# ─────────────────────────────────────────────────────────
async def _startup_common() -> Tuple[Bot, Dispatcher, Optional[Any]]:
    logger.info("📦 Initializing database…")
    await init_db()

    _maybe_setup_sentry()

    bot = Bot(
        token=settings.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # صحت‌سنجی توکن/اتصال
    try:
        me = await bot.get_me()
        logger.info("🤖 Bot authorized: @%s (id=%s)", me.username, me.id)
    except Exception as e:
        logger.critical("🚫 Telegram authorization failed: %s", e, exc_info=True)
        with suppress(Exception):
            await bot.session.close()
        raise

    storage, redis_client = await _resolve_storage()
    dp = Dispatcher(storage=storage, fsm_strategy=FSMStrategy.CHAT)

    _include_routers(dp)
    await _maybe_setup_bot_commands(bot)

    return bot, dp, redis_client


# ─────────────────────────────────────────────────────────
# 🔁 Polling
# ─────────────────────────────────────────────────────────
async def _run_polling(bot: Bot, dp: Dispatcher) -> None:
    logger.info("🔁 Starting in Long Polling mode…")

    # حذف وبهوک قبلی و Drop آپدیت‌های معلق
    with suppress(Exception):
        await bot.delete_webhook(drop_pending_updates=True)

    try:
        allowed_updates = dp.resolve_used_update_types()
        if not allowed_updates:
            raise ValueError("empty")
    except Exception:
        allowed_updates = ["message", "callback_query"]

    logger.debug("Allowed updates: %s", allowed_updates)

    await dp.start_polling(bot, allowed_updates=allowed_updates)


# ─────────────────────────────────────────────────────────
# 🌐 Webhook (AIOHTTP)
# ─────────────────────────────────────────────────────────
async def _run_webhook(bot: Bot, dp: Dispatcher) -> None:
    if web is None:
        raise RuntimeError("aiohttp is not available. Install it or disable WEBHOOK_MODE.")
    if not settings.webhook_url:
        raise ValueError("WEBHOOK_MODE=True but webhook_url is not configured properly.")

    logger.info("🌐 Starting in Webhook mode at %s", settings.webhook_url)

    app = web.Application()

    # مسیر سلامت ساده
    async def health(_req):
        return web.json_response({"ok": True})
    app.router.add_get("/healthz", health)

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


# ─────────────────────────────────────────────────────────
# 🧬 چرخهٔ عمر (سیگنال‌ها، cleanup)
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def _lifespan(bot: Bot, dp: Dispatcher, redis_client: Optional[Any]):
    loop = asyncio.get_running_loop()

    def _stop_signal(signame: str):
        logger.warning("🛑 Received %s -> shutting down…", signame)

    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _stop_signal, sig.name)

    try:
        yield
    finally:
        logger.info("🔻 Closing bot, storage and DB…")
        with suppress(Exception):
            await dp.storage.close()
        if redis_client is not None:
            with suppress(Exception):
                await redis_client.close()
        with suppress(Exception):
            await bot.session.close()
        with suppress(Exception):
            await shutdown_db()


# ─────────────────────────────────────────────────────────
# 🏁 Entry point
# ─────────────────────────────────────────────────────────
async def start_bot() -> None:
    """
    ورودی اصلی اپ. بات را در حالت Polling یا Webhook بالا می‌آورد.
    """
    bot, dp, redis_client = await _startup_common()
    logger.info("✅ Bot is ready to receive updates.")

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(_lifespan(bot, dp, redis_client))

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
