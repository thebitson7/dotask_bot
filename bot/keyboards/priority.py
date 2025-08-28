# bot/keyboards/priority.py
from __future__ import annotations

from functools import lru_cache
from typing import Iterable, Optional, Sequence, Tuple

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.config import get_settings
from database.models import TaskPriority

settings = get_settings()

# ─────────────────────────────────────────────
# 🌍 ترجمه‌ها (fa/en) + اموجی
# کلیدها برابر name های Enum هستند: HIGH / MEDIUM / LOW
# ─────────────────────────────────────────────
_I18N: dict[str, dict[str, str]] = {
    "fa": {
        "HIGH": "🔴 بالا",
        "MEDIUM": "🟡 متوسط",
        "LOW": "🟢 پایین",
    },
    "en": {
        "HIGH": "🔴 High",
        "MEDIUM": "🟡 Medium",
        "LOW": "🟢 Low",
    },
}

# ترتیب پیش‌فرض (High → Low)
_DEFAULT_ORDER: Tuple[str, ...] = ("HIGH", "MEDIUM", "LOW")

# حداکثر طول مجاز برای callback_data در تلگرام
_CALLBACK_MAX = 64


def _norm_lang(code: Optional[str]) -> Optional[str]:
    return (code or "").strip().lower() or None


def _fallback_chain(preferred: Optional[str]) -> list[str]:
    """
    چینِ fallback: [lang, DEFAULT_LANG, LOCALE_FALLBACKS..., 'fa', 'en'] (بدون تکرار)
    """
    chain: list[str] = []
    seen: set[str] = set()

    def add(c: Optional[str]) -> None:
        c = _norm_lang(c)
        if c and c not in seen:
            seen.add(c)
            chain.append(c)

    add(preferred)
    add(settings.DEFAULT_LANG)
    for fb in settings.LOCALE_FALLBACKS:
        add(fb)
    # fallback سخت
    add("fa")
    add("en")
    return chain


def _labels_for(lang: Optional[str]) -> dict[str, str]:
    """
    لیبل‌های نهایی با توجه به fallback chain.
    اگر ترجمه‌ای نبود، از en استفاده می‌شود.
    """
    out: dict[str, str] = {}
    for code in _fallback_chain(lang):
        out.update(_I18N.get(code, {}))
    # اطمینان از وجود همه‌ی کلیدها
    for key in _DEFAULT_ORDER:
        out.setdefault(key, _I18N["en"][key])
    return out


def _to_name(val: TaskPriority | str) -> str:
    return val.name if isinstance(val, TaskPriority) else str(val).upper()


def priority_label(priority: TaskPriority | str, *, lang: Optional[str] = None) -> str:
    """
    برگرداندن لیبل قابل‌نمایش برای یک اولویت (با اموجی).
    """
    name = _to_name(priority)
    return _labels_for(lang).get(name, name.title())


def priority_callback_data(priority: TaskPriority | str, prefix: str = "priority:") -> str:
    """
    ساخت callback_data استاندارد برای یک اولویت. (مثل: 'priority:HIGH')
    """
    name = _to_name(priority)
    data = f"{prefix}{name}"
    # تضمین طول مجاز
    if len(data) > _CALLBACK_MAX:
        raise ValueError(f"callback_data too long ({len(data)}>{_CALLBACK_MAX}): {data!r}")
    return data


def parse_priority_from_callback(data: str, prefix: str = "priority:") -> Optional[TaskPriority]:
    """
    پارس کردن callback_data و برگرداندن TaskPriority یا None.
    """
    if not data.startswith(prefix):
        return None
    name = data[len(prefix):].strip().upper()
    try:
        return TaskPriority[name]
    except Exception:
        return None


# ─────────────────────────────────────────────
# 🧠 هستهٔ سازندهٔ کیبورد (کش‌شده)
# ─────────────────────────────────────────────
@lru_cache(maxsize=256)
def _cached_priority_keyboard(
    lang: Optional[str],
    allowed_names: Tuple[str, ...],
    order_names: Tuple[str, ...],
    columns: int,
    prefix: str,
) -> InlineKeyboardMarkup:
    labels = _labels_for(lang)

    # ترتیب: ابتدا طبق order، سپس بقیه‌ی allowed که در order نیامده‌اند
    ordered: list[str] = [n for n in order_names if n in allowed_names]
    for n in allowed_names:
        if n not in ordered:
            ordered.append(n)

    builder = InlineKeyboardBuilder()
    for name in ordered:
        text = labels.get(name, name.title())
        callback = f"{prefix}{name}"
        if len(callback) > _CALLBACK_MAX:
            # در عمل این اتفاق نمی‌افتد، ولی برای کمال‌گرایی
            raise ValueError(f"callback_data too long ({len(callback)}>{_CALLBACK_MAX}): {callback!r}")
        builder.button(text=text, callback_data=callback)

    builder.adjust(max(1, int(columns) if columns and columns > 0 else 1))
    return builder.as_markup()


# ─────────────────────────────────────────────
# 🎛️ کیبورد اینلاین انتخاب اولویت
# ─────────────────────────────────────────────
def priority_keyboard(
    *,
    lang: Optional[str] = None,
    allowed: Optional[Iterable[TaskPriority | str]] = None,
    order: Optional[Sequence[TaskPriority | str]] = None,
    columns: int = 3,
    prefix: str = "priority:",
) -> InlineKeyboardMarkup:
    """
    تولید کیبورد اینلاین برای انتخاب اولویت.

    پارامترها:
      - lang: زبان متن دکمه‌ها (None → از settings و fallback استفاده می‌شود)
      - allowed: مجموعهٔ اولویت‌های مجاز (پیش‌فرض: همهٔ enumها)
      - order: ترتیب دلخواه نمایش (بقیهٔ allowed ها انتهای لیست می‌آیند)
      - columns: تعداد ستون‌ها (پیش‌فرض 3)
      - prefix: پیش‌وند callback_data (پیش‌فرض "priority:")

    مثال‌ها:
      priority_keyboard()
      priority_keyboard(lang="en", columns=2)
      priority_keyboard(allowed=[TaskPriority.HIGH, TaskPriority.LOW], order=[TaskPriority.LOW, TaskPriority.HIGH])
    """
    # آماده‌سازی نام‌ها برای کش (hashable)
    if allowed is None:
        allowed_names = tuple(p.name for p in TaskPriority)  # HIGH, MEDIUM, LOW
    else:
        allowed_names = tuple(_to_name(p) for p in allowed)

    if order is None:
        order_names = _DEFAULT_ORDER
    else:
        order_names = tuple(_to_name(p) for p in order)

    return _cached_priority_keyboard(
        _norm_lang(lang),
        allowed_names=allowed_names,
        order_names=order_names,
        columns=columns,
        prefix=prefix,
    )


__all__ = [
    "priority_keyboard",
    "priority_label",
    "priority_callback_data",
    "parse_priority_from_callback",
]
