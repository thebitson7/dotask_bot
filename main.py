# main.py
from __future__ import annotations

import asyncio
import logging
import os
import platform
from typing import Optional

from core.config import get_settings
from core.startup import start_bot
from database.session import shutdown_db


# ─────────────────────────────────────────────
# 🔧 Logging Setup (Rich-aware, Sentry-aware)
# ─────────────────────────────────────────────
def setup_logging() -> None:
    settings = get_settings()

    # Try Rich handler (optional, nice in dev)
    handler: Optional[logging.Handler] = None
    try:
        from rich.logging import RichHandler  # type: ignore
        handler = RichHandler(rich_tracebacks=True, tracebacks_suppress=[asyncio], show_path=False)
    except Exception:
        handler = logging.StreamHandler()

    logging.basicConfig(
        level=getattr(logging, settings.effective_log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[handler],
    )

    # Reduce noisy loggers
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiogram.client.session").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

    # Optional Sentry
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk  # type: ignore
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                traces_sample_rate=0.1 if settings.is_prod else 0.0,  # adjust as you like
                profiles_sample_rate=0.0,
                environment=settings.ENV,
                release=os.getenv("RELEASE", None),
            )
            logging.getLogger(__name__).info("🛰 Sentry initialized.")
        except Exception as e:
            logging.getLogger(__name__).warning("Sentry init failed: %s", e)


# ─────────────────────────────────────────────
# 🚀 Bot Runner
# ─────────────────────────────────────────────
async def run_bot() -> None:
    settings = get_settings()
    # asyncio debug useful in dev
    if settings.DEBUG:
        asyncio.get_running_loop().set_debug(True)
    await start_bot()


# ─────────────────────────────────────────────
# ⏹️ Entrypoint
# ─────────────────────────────────────────────
def _maybe_set_uvloop() -> None:
    # Use uvloop if available and not on Windows
    if platform.system().lower().startswith("win"):
        return
    try:
        import uvloop  # type: ignore
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        logging.getLogger(__name__).info("⚡ uvloop enabled.")
    except Exception:
        # silently ignore if not installed
        pass


def main() -> None:
    setup_logging()
    logger = logging.getLogger("DoTask")

    _maybe_set_uvloop()

    try:
        logger.info("🚀 Launching bot…")
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.warning("🛑 Bot stopped manually.")
    except Exception:
        logger.exception("💥 Unhandled exception")
    finally:
        # Ensure DB engine is disposed cleanly
        try:
            asyncio.run(shutdown_db())
        except Exception:
            logger.exception("⚠️ Failed to shutdown DB cleanly")


if __name__ == "__main__":
    main()
