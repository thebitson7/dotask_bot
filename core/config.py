# core/config.py
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import os
import re
from pydantic import (
    Field,
    SecretStr,
    ValidationInfo,
    computed_field,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from zoneinfo import ZoneInfo


_VALID_DB_SCHEMES = (
    "sqlite+aiosqlite",
    "postgresql+asyncpg",
    "postgresql+psycopg",      # psycopg3 (async)
    "mysql+aiomysql",
    "mssql+aioodbc",
    "mssql+pytds",
    "oracle+oracledb",
)


def _csv(var: Optional[str]) -> list[str]:
    """Parse comma/space separated env values -> list[str], dedup while keeping order."""
    if not var:
        return []
    parts = [p.strip() for p in re.split(r"[,\s]+", var) if p.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


class Settings(BaseSettings):
    """
    🔧 Global Configuration
    Values load from environment (.env + OS env).
    """

    # ───────────── Telegram ─────────────
    BOT_TOKEN: SecretStr = Field(..., description="Telegram Bot Token, format: '<id>:<hash>'")
    WEBHOOK_MODE: bool = Field(default=False, description="Use Telegram webhook instead of long polling")
    WEBHOOK_DOMAIN: Optional[str] = Field(default=None, description="Public domain for webhook, e.g. example.com")
    WEBHOOK_SCHEME: Literal["https", "http"] = "https"
    WEBHOOK_PATH: str = Field(default="/telegram/webhook", description="Webhook relative path")
    WEBHOOK_SECRET: Optional[str] = Field(default=None, description="Optional secret token for Telegram webhook")

    # ───────────── Server (for webhook) ─────────────
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8080, ge=1, le=65535)

    # ───────────── Database ─────────────
    DB_URL: str = Field(
        default="sqlite+aiosqlite:///db.sqlite3",
        description="SQLAlchemy async URL, e.g. sqlite+aiosqlite:///db.sqlite3 or postgresql+asyncpg://user:pass@host:5432/db",
    )
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = Field(default=10, ge=1)
    DB_POOL_TIMEOUT: int = Field(default=30, ge=1)  # seconds
    DB_POOL_RECYCLE: int = Field(default=1800, ge=0, description="Seconds to recycle pooled connections")
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0)

    # ───────────── Cache / Queue (اختیاری) ─────────────
    REDIS_URL: Optional[str] = Field(default=None, description="redis://localhost:6379/0")

    # ───────────── Environment ─────────────
    ENV: Literal["development", "production", "test"] = "development"
    DEBUG: Optional[bool] = Field(default=None, description="If not set, inferred: ENV!=production -> True")
    LOG_LEVEL: Optional[Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"]] = None

    # ───────────── Localization ─────────────
    DEFAULT_LANG: Literal["fa", "en"] = "fa"
    TZ: str = "Asia/Tehran"
    SUPPORTED_LOCALES: list[str] = Field(default_factory=lambda: ["fa", "en"], description="Supported locale tags")
    LOCALE_FALLBACKS: list[str] = Field(default_factory=list, description="Optional fallbacks (highest priority first)")

    # ───────────── Observability (اختیاری) ─────────────
    SENTRY_DSN: Optional[str] = None

    # ───────────── Rate limiting (مثال) ─────────────
    RATE_LIMIT_GLOBAL_PER_MIN: int = Field(default=900, ge=1)  # across all users
    RATE_LIMIT_PER_CHAT_PER_MIN: int = Field(default=60, ge=1)

    # ───────────── Pydantic Meta ─────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_nested_delimiter="__",
    )

    # ───────────── Validators ─────────────
    @field_validator("BOT_TOKEN", mode="before")
    @classmethod
    def _v_bot_token(cls, v: str | SecretStr) -> SecretStr:
        """Basic sanity check for Telegram token (<digits>:<hash>)."""
        raw = v.get_secret_value() if isinstance(v, SecretStr) else str(v or "")
        if ":" not in raw or not raw.split(":", 1)[0].isdigit():
            raise ValueError("Invalid BOT_TOKEN format. Expected '<bot_id>:<secret>'.")
        return SecretStr(raw)

    @field_validator("TZ")
    @classmethod
    def _v_tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)  # raises if invalid
            return v
        except Exception as e:
            raise ValueError(f"Invalid timezone '{v}': {e}") from e

    @field_validator("DB_URL")
    @classmethod
    def _v_db_url(cls, v: str) -> str:
        if not isinstance(v, str) or "://" not in v:
            raise ValueError("DB_URL must be a valid SQLAlchemy async URL.")
        scheme = v.split("://", 1)[0]
        if scheme not in _VALID_DB_SCHEMES:
            valid = ", ".join(_VALID_DB_SCHEMES)
            raise ValueError(f"Unsupported DB scheme '{scheme}'. Valid: {valid}")
        if scheme.startswith("sqlite"):
            v = v.replace("\\", "/")
        return v

    @field_validator("SUPPORTED_LOCALES", mode="before")
    @classmethod
    def _v_supported_locales(cls, v):
        """
        Accept JSON list, python list/tuple/set, or CSV/space-separated string.
        """
        if isinstance(v, (list, tuple, set)):
            out = [str(x).strip() for x in v if str(x).strip()]
        else:
            out = _csv(str(v) if v is not None else "")
        if not out:
            out = ["fa", "en"]
        # dedupe while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for item in out:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped

    @field_validator("LOCALE_FALLBACKS", mode="before")
    @classmethod
    def _v_fallbacks(cls, v: list[str] | str | None) -> list[str]:
        if isinstance(v, (list, tuple, set)):
            return [str(x).strip() for x in v if str(x).strip()]
        return _csv(v)

    @field_validator("WEBHOOK_DOMAIN")
    @classmethod
    def _v_webhook_domain(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        dom = v.strip()
        # نباید scheme داشته باشد؛ فقط دامنه/دامنه:پورت
        if dom.startswith("http://") or dom.startswith("https://"):
            raise ValueError("WEBHOOK_DOMAIN must be domain only (e.g. 'example.com'), not a full URL.")
        # حذف اسلش انتهایی
        return dom.rstrip("/")

    @field_validator("WEBHOOK_PATH", mode="before")
    @classmethod
    def _v_webhook_path(cls, v: str) -> str:
        # به صورت canonical: با یک / شروع شود، اسلش‌های اضافی حذف
        p = "/" + str(v or "").strip().lstrip("/")
        return p

    def model_post_init(self, __context: ValidationInfo) -> None:
        if self.DEBUG is None:
            object.__setattr__(self, "DEBUG", self.ENV != "production")
        if self.LOG_LEVEL is None:
            object.__setattr__(self, "LOG_LEVEL", "DEBUG" if self.DEBUG else "INFO")
        if self.WEBHOOK_MODE and not self.WEBHOOK_DOMAIN:
            raise ValueError("WEBHOOK_MODE=True requires WEBHOOK_DOMAIN to be set (public domain).")
        # اطمینان: DEFAULT_LANG جزو SUPPORTED_LOCALES باشد
        if self.DEFAULT_LANG not in self.SUPPORTED_LOCALES:
            self.SUPPORTED_LOCALES.append(self.DEFAULT_LANG)

    # ───────────── Computed fields / helpers ─────────────
    @computed_field  # type: ignore[misc]
    @property
    def is_dev(self) -> bool:
        return self.ENV == "development"

    @computed_field  # type: ignore[misc]
    @property
    def is_prod(self) -> bool:
        return self.ENV == "production"

    @computed_field  # type: ignore[misc]
    @property
    def is_test(self) -> bool:
        return self.ENV == "test"

    @computed_field  # type: ignore[misc]
    @property
    def BASE_DIR(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @computed_field  # type: ignore[misc]
    @property
    def LOCALES_DIR(self) -> Path:
        return self.BASE_DIR / "locales"

    @computed_field  # type: ignore[misc]
    @property
    def TZINFO(self) -> ZoneInfo:
        # مصرف این در کد: settings.TZINFO
        return ZoneInfo(self.TZ)

    @computed_field  # type: ignore[misc]
    @property
    def effective_log_level(self) -> str:
        return self.LOG_LEVEL or ("DEBUG" if self.DEBUG else "INFO")

    @computed_field  # type: ignore[misc]
    @property
    def db_is_sqlite(self) -> bool:
        return self.DB_URL.startswith("sqlite+aiosqlite://")

    @computed_field  # type: ignore[misc]
    @property
    def redis_enabled(self) -> bool:
        return bool(self.REDIS_URL and self.REDIS_URL.strip())

    @computed_field  # type: ignore[misc]
    @property
    def webhook_url(self) -> Optional[str]:
        if not self.WEBHOOK_MODE or not self.WEBHOOK_DOMAIN:
            return None
        # WEBHOOK_DOMAIN قبلاً بدون scheme ذخیره شده
        domain = self.WEBHOOK_DOMAIN
        path = self.WEBHOOK_PATH  # canonical از validator
        return f"{self.WEBHOOK_SCHEME}://{domain}{path}"

    def as_safe_dict(self) -> dict:
        """Sanitized dict for logging (secrets masked)."""
        data = self.model_dump()
        data["BOT_TOKEN"] = "****"
        return data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    📦 Cached settings instance.
    """
    settings = Settings()
    # Optional: normalize CWD to project root (useful in Docker)
    try:
        os.chdir(settings.BASE_DIR)
    except Exception:
        pass
    return settings
