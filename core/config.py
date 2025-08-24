# core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    🔧 Global Project Configuration
    Load all settings from `.env` file or system environment variables.
    """

    # ─── Telegram Bot ───────────────
    BOT_TOKEN: str  # 🔐 REQUIRED: Telegram Bot API token

    # ─── Database Config ────────────
    DB_URL: str = "sqlite+aiosqlite:///db.sqlite3"  # ✅ Default to local SQLite (dev/test)

    # ─── Environment & Debug ────────
    ENV: str = "development"  # Options: development | production | test
    DEBUG: bool = False

    # ─── Localization ───────────────
    DEFAULT_LANG: str = "fa"
    TZ: str = "Asia/Tehran"

    # ─── Model Config ───────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def is_dev(self) -> bool:
        return self.ENV == "development"

    @property
    def is_prod(self) -> bool:
        return self.ENV == "production"

    @property
    def is_test(self) -> bool:
        return self.ENV == "test"


@lru_cache()
def get_settings() -> Settings:
    """
    📦 Cached Singleton to access settings globally.
    Use `get_settings()` anywhere in the app to fetch current config.
    """
    return Settings()
