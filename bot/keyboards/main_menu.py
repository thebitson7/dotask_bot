# bot/keyboards/main_menu.py

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


# ─────────────────────────────────────────────
# 🎛 دکمه‌های اصلی به صورت ثابت
# برای چندزبانه بودن، بهتر است از فایل locale خوانده شود.
# ─────────────────────────────────────────────
class MainMenuButtons:
    ADD_TASK = "➕ افزودن تسک"
    LIST_TASKS = "📋 لیست وظایف"
    SETTINGS = "⚙️ تنظیمات"
    HELP = "ℹ️ راهنما"


# ─────────────────────────────────────────────
# 🧱 ساختار کیبورد منوی اصلی
# ─────────────────────────────────────────────
def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    📲 تولید کیبورد اصلی با چیدمان دو سطری:
    ➤ قابل استفاده در /start و بازگشت به منو
    """

    layout = [
        [
            KeyboardButton(text=MainMenuButtons.ADD_TASK),
            KeyboardButton(text=MainMenuButtons.LIST_TASKS)
        ],
        [
            KeyboardButton(text=MainMenuButtons.SETTINGS),
            KeyboardButton(text=MainMenuButtons.HELP)
        ]
    ]

    return ReplyKeyboardMarkup(
        keyboard=layout,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="🔘 لطفاً یکی از گزینه‌ها را انتخاب کن..."
    )
