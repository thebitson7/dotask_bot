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
    تولید کیبورد برای منوی اصلی با ساختار مرتب و رسپانسیو.
    - دو ردیف، هر کدام دو دکمه
    - سازگار با موبایل
    - placeholder جهت راهنمایی کاربر
    """
    keyboard = [
        [KeyboardButton(text=BTN_ADD_TASK), KeyboardButton(text=BTN_LIST_TASKS)],
        [KeyboardButton(text=BTN_SETTINGS), KeyboardButton(text=BTN_HELP)],
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,  # ⬅️ برای نمایش بهتر در موبایل
        one_time_keyboard=False,
        input_field_placeholder="🔘 لطفاً یکی از گزینه‌ها را انتخاب کنید..."
    )
