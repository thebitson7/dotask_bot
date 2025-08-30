# bot/keyboards/main_menu.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ─────────────────────────────────────────
# 🏷️ Labels (fa-first؛ قابل گسترش به en)
# ─────────────────────────────────────────
@dataclass(frozen=True)
class MainMenuButtons:
    ADD_TASK: str = "➕ افزودن تسک"
    LIST_TASKS: str = "📋 لیست تسک‌ها"
    SETTINGS: str = "⚙️ تنظیمات"
    HELP: str = "ℹ️ راهنما"
    SEARCH: str = "🔎 جستجو"
    FILTER_TODAY: str = "⚡️ امروز"
    FILTER_OVERDUE: str = "⏰ گذشته"


# ─────────────────────────────────────────
# 🔤 Aliases / Triggers (نرمال‌سازی پایین)
# ─────────────────────────────────────────
def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


ADD_TASK_ALIASES: set[str] = {
    MainMenuButtons.ADD_TASK,
    "➕ افزودن تسک",
    "افزودن تسک", "تسک جدید",
    "add task", "new task", "add",
}

LIST_TASKS_ALIASES: set[str] = {
    MainMenuButtons.LIST_TASKS,
    "📋 لیست تسک‌ها", "لیست تسک‌ها", "لیست وظایف",
    "tasks", "my tasks", "list tasks",
}

SETTINGS_ALIASES: set[str] = {
    MainMenuButtons.SETTINGS, "settings", "تنظیمات",
}

HELP_ALIASES: set[str] = {
    MainMenuButtons.HELP, "help", "راهنما",
}

SEARCH_ALIASES: set[str] = {
    MainMenuButtons.SEARCH, "search", "جستجو", "🔎 جستجو",
}

FILTER_TODAY_ALIASES: set[str] = {
    MainMenuButtons.FILTER_TODAY, "today", "امروز", "⚡️ امروز",
}

FILTER_OVERDUE_ALIASES: set[str] = {
    MainMenuButtons.FILTER_OVERDUE, "overdue", "گذشته", "⏰ گذشته",
}


def is_add_task(text: Optional[str]) -> bool:
    t = _norm(text)
    return any(t == _norm(x) for x in ADD_TASK_ALIASES)


def is_list_tasks(text: Optional[str]) -> bool:
    t = _norm(text)
    return any(t == _norm(x) for x in LIST_TASKS_ALIASES)


def is_settings(text: Optional[str]) -> bool:
    t = _norm(text)
    return any(t == _norm(x) for x in SETTINGS_ALIASES)


def is_help(text: Optional[str]) -> bool:
    t = _norm(text)
    return any(t == _norm(x) for x in HELP_ALIASES)


def is_search(text: Optional[str]) -> bool:
    t = _norm(text)
    return any(t == _norm(x) for x in SEARCH_ALIASES)


def is_filter_today(text: Optional[str]) -> bool:
    t = _norm(text)
    return any(t == _norm(x) for x in FILTER_TODAY_ALIASES)


def is_filter_overdue(text: Optional[str]) -> bool:
    t = _norm(text)
    return any(t == _norm(x) for x in FILTER_OVERDUE_ALIASES)


# ─────────────────────────────────────────
# 🧮 Helpers برای لیبل‌های شمارنده
# ─────────────────────────────────────────
def _fmt_tasks_badge(base: str, open_count: Optional[int], done_count: Optional[int]) -> str:
    """
    اگر شمارنده‌ها آمدند، درون لیبل «لیست» نمایش بده.
    مثال:  📋 لیست تسک‌ها (3/10)
           (open/done)
    """
    if open_count is None and done_count is None:
        return base
    oc = max(0, int(open_count or 0))
    dc = max(0, int(done_count or 0))
    return f"{base} ({oc}/{dc})"


# ─────────────────────────────────────────
# 🎛️ کیبورد اصلی
# ─────────────────────────────────────────
def main_menu_keyboard(
    *,
    open_count: Optional[int] = None,
    done_count: Optional[int] = None,
    include_quick_row: bool = True,
) -> ReplyKeyboardMarkup:
    """
    سازگار با گذشته: بدون آرگومان هم قابل‌استفاده است.
    - open_count/done_count → اگر بدهی، رو لیبل «📋 لیست تسک‌ها» نشان می‌دهیم.
    - include_quick_row → ردیف میان‌بُرها (جستجو/امروز/گذشته).
    """
    add_btn = KeyboardButton(text=MainMenuButtons.ADD_TASK)
    list_btn = KeyboardButton(text=_fmt_tasks_badge(MainMenuButtons.LIST_TASKS, open_count, done_count))
    settings_btn = KeyboardButton(text=MainMenuButtons.SETTINGS)
    help_btn = KeyboardButton(text=MainMenuButtons.HELP)

    layout: list[list[KeyboardButton]] = [
        [add_btn, list_btn],
    ]

    if include_quick_row:
        layout.append([
            KeyboardButton(text=MainMenuButtons.SEARCH),
            KeyboardButton(text=MainMenuButtons.FILTER_TODAY),
            KeyboardButton(text=MainMenuButtons.FILTER_OVERDUE),
        ])

    layout.append([settings_btn, help_btn])

    return ReplyKeyboardMarkup(
        keyboard=layout,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="🔘 لطفاً یکی از گزینه‌ها را انتخاب کن…",
    )


__all__ = [
    "MainMenuButtons",
    "main_menu_keyboard",
    # match helpers
    "is_add_task", "is_list_tasks", "is_settings", "is_help",
    "is_search", "is_filter_today", "is_filter_overdue",
    # alias sets (اگر جایی لازم شد)
    "ADD_TASK_ALIASES", "LIST_TASKS_ALIASES",
    "SETTINGS_ALIASES", "HELP_ALIASES",
    "SEARCH_ALIASES", "FILTER_TODAY_ALIASES", "FILTER_OVERDUE_ALIASES",
]
