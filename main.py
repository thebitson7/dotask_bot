# main.py
from __future__ import annotations

import asyncio
import logging
import platform
from typing import Optional

from core.config import get_settings
from core.startup import start_bot


# ─────────────────────────────────────────────
# 🔧 Logging Setup (Rich-aware)
# ─────────────────────────────────────────────
def setup_logging() -> None:
    """
    پیکربندی لاگینگ:
    - سعی می‌کند RichHandler را استفاده کند (در صورت نصب)
    - سطح لاگ را از Settings می‌خواند
    - لاگرهای پرنویز را کم‌سر و صدا می‌کند
    """
    settings = get_settings()

    # اگر قبلاً کانفیگ شده، دوباره پیکربندی نکن
    if logging.getLogger().handlers:
        return

    handler: Optional[logging.Handler]
    try:
        from rich.logging import RichHandler  # type: ignore
        handler = RichHandler(
            rich_tracebacks=True,
            tracebacks_suppress=[asyncio],
            show_path=False,
            markup=True,
        )
    except Exception:
        handler = logging.StreamHandler()

    logging.basicConfig(
        level=getattr(logging, settings.effective_log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[handler],
    )

    # کاهش نویز
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiogram.client.session").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)


# ─────────────────────────────────────────────
# ⚡ uvloop (اختیاری)
# ─────────────────────────────────────────────
def _maybe_set_uvloop() -> None:
    """روی سیستم‌های غیر ویندوز، اگر uvloop نصب بود، فعالش می‌کنیم."""
    if platform.system().lower().startswith("win"):
        return
    try:
        import uvloop  # type: ignore
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        logging.getLogger(__name__).info("⚡ uvloop enabled.")
    except Exception:
        # نصب نیست یا در محیط فعلی قابل‌استفاده نیست → نادیده بگیر
        pass


# ─────────────────────────────────────────────
# 🚀 Bot Runner
# ─────────────────────────────────────────────
async def run_bot() -> None:
    settings = get_settings()
    if settings.DEBUG:
        asyncio.get_running_loop().set_debug(True)
    await start_bot()


# ─────────────────────────────────────────────
# ⏹️ Entrypoint
# ─────────────────────────────────────────────
def main() -> None:
    setup_logging()
    logger = logging.getLogger("DoTask")

    _maybe_set_uvloop()

    try:
        logger.info("🚀 Launching bot…")
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.warning("🛑 Bot stopped.")
    except Exception:
        logger.exception("💥 Unhandled exception")


if __name__ == "__main__":
    main()
