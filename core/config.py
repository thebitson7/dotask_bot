# core/config.py

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    🔧 Global Configuration for the Project
    Reads from .env file and environment variables.
    """

    # ───────────── Telegram ─────────────
    BOT_TOKEN: str  # 🔐 REQUIRED: Telegram Bot Token

    # ───────────── Database ─────────────
    DB_URL: str = "sqlite+aiosqlite:///db.sqlite3"  # 💾 Default: local SQLite

    # ───────────── Environment ─────────────
    ENV: str = "development"  # Options: development | production | test
    DEBUG: bool = False

    # ───────────── Localization ─────────────
    DEFAULT_LANG: str = "fa"
    TZ: str = "Asia/Tehran"

    # ───────────── Pydantic Meta ─────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # ⛑ Ignore unknown env vars
    )

    # ───────────── Helper Flags ─────────────
    @property
    def is_dev(self) -> bool:
        return self.ENV.lower() == "development"

    @property
    def is_prod(self) -> bool:
        return self.ENV.lower() == "production"

    @property
    def is_test(self) -> bool:
        return self.ENV.lower() == "test"


# ───────────── Singleton for Global Access ─────────────
@lru_cache()
def get_settings() -> Settings:
    """
    📦 Global cached config.
    Usage: settings = get_settings()
    """
    return Settings()
