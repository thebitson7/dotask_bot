# main.py

import asyncio
import logging
from core.startup import start_bot
from core.config import get_settings


# ─────────────────────────────────────────────
# 🔧 Logging Setup
# ─────────────────────────────────────────────
def setup_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=logging.DEBUG if settings.is_dev else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)  # Aiogram noise suppression


# ─────────────────────────────────────────────
# 🚀 Bot Entry Point
# ─────────────────────────────────────────────
async def run_bot():
    await start_bot()


# ─────────────────────────────────────────────
# ⏹️ Run Script
# ─────────────────────────────────────────────
if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger("DoTask")

    try:
        logger.info("🚀 Launching bot...")
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.warning("🛑 Bot stopped manually.")
    except Exception as e:
        logger.exception(f"💥 Unhandled exception: {e}")
