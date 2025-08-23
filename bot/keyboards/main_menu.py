from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# 🧩 دکمه‌ها
BTN_ADD_TASK = "➕ افزودن تسک"
BTN_LIST_TASKS = "📋 لیست تسک‌ها"
BTN_SETTINGS = "⚙️ تنظیمات"
BTN_HELP = "ℹ️ راهنمای استفاده"

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    منوی اصلی به‌روزرسانی‌شده با ظاهری منظم و حرفه‌ای‌تر.
    """

    keyboard = [
        [KeyboardButton(text=BTN_ADD_TASK), KeyboardButton(text=BTN_LIST_TASKS)],
        [KeyboardButton(text=BTN_SETTINGS), KeyboardButton(text=BTN_HELP)],
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="🔘 یکی از گزینه‌ها رو از منو انتخاب کن..."
    )
