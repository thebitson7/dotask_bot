from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    تنظیمات اصلی پروژه Dotask Bot
    مقادیر از فایل `.env` یا متغیرهای محیطی سیستم بارگذاری می‌شوند.
    """

    # --- تنظیمات ربات ---
    BOT_TOKEN: str  # توکن ربات تلگرام (اجباری)

    # --- دیتابیس ---
    DB_URL: str = "sqlite+aiosqlite:///db.sqlite3"

    # --- تنظیمات پیش‌فرض ---
    DEFAULT_LANG: str = "fa"
    TZ: str = "Asia/Tehran"

    # --- حالت اجرا (اختیاری، برای آینده) ---
    ENV: str = "development"  # development | production | test

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache()
def get_settings() -> Settings:
    """
    دریافت تنظیمات به‌صورت singleton (کش شده)
    """
    return Settings()
