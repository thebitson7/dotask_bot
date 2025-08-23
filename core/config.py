# core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    🔧 Project Configuration for Dotask Bot
    
    All values are loaded from the `.env` file or system environment variables.
    Easily switchable between environments like: development, production, test.
    """

    # ─────[ Telegram Bot ]─────
    BOT_TOKEN: str  # ✅ Required: Telegram Bot Token

    # ─────[ Database ]─────
    DB_URL: str = "sqlite+aiosqlite:///db.sqlite3"  # Default to local SQLite

    # ─────[ Defaults ]─────
    DEFAULT_LANG: str = "fa"
    TZ: str = "Asia/Tehran"

    # ─────[ Environment ]─────
    ENV: str = "development"  # Options: development | production | test

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore unknown env vars
    )


@lru_cache()
def get_settings() -> Settings:
    """
    📦 Singleton accessor for project settings
    (using LRU cache for efficiency)
    """
    return Settings()
