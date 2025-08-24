# bot/keyboards/main_menu.py

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ─────────────────────────────────────────────
# 🎛 دکمه‌های منوی اصلی
# ─────────────────────────────────────────────
BTN_ADD_TASK = "➕ افزودن تسک"
BTN_LIST_TASKS = "📋 لیست وظایف"
BTN_SETTINGS = "⚙️ تنظیمات"
BTN_HELP = "ℹ️ راهنما"


# ─────────────────────────────────────────────
# 📲 ساخت کیبورد منوی اصلی
# ─────────────────────────────────────────────
def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    ✅ تولید کیبورد اصلی:
    - ساختار ۲×۲ برای تجربه کاربری عالی
    - ظاهر منظم و تطبیق‌پذیر با دستگاه‌های مختلف
    - پیام placeholder جهت هدایت کاربر
    """
    keyboard_layout = [
        [
            KeyboardButton(text=BTN_ADD_TASK),
            KeyboardButton(text=BTN_LIST_TASKS)
        ],
        [
            KeyboardButton(text=BTN_SETTINGS),
            KeyboardButton(text=BTN_HELP)
        ]
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard_layout,
        resize_keyboard=True,             # برای واکنش‌گرایی بهتر
        one_time_keyboard=False,          # همیشه در دسترس
        input_field_placeholder="🔘 یک گزینه را انتخاب کن..."
    )
