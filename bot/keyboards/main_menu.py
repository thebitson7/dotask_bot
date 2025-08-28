from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

class MainMenuButtons:
    ADD_TASK = "➕ افزودن تسک"
    LIST_TASKS = "📋 لیست وظایف"
    SETTINGS = "⚙️ تنظیمات"
    HELP = "ℹ️ راهنما"

# alias برای چند زبان/بدون ایموجی
ADD_TASK_ALIASES = {
    MainMenuButtons.ADD_TASK,
    "افزودن تسک", "تسک جدید", "add task", "new task", "add",
}
LIST_TASKS_ALIASES = {
    MainMenuButtons.LIST_TASKS,
    "لیست وظایف", "لیست تسک‌ها", "tasks", "my tasks", "list tasks",
}
SETTINGS_ALIASES = {MainMenuButtons.SETTINGS, "settings", "تنظیمات"}
HELP_ALIASES = {MainMenuButtons.HELP, "help", "راهنما"}

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    layout = [
        [KeyboardButton(text=MainMenuButtons.ADD_TASK),
         KeyboardButton(text=MainMenuButtons.LIST_TASKS)],
        [KeyboardButton(text=MainMenuButtons.SETTINGS),
         KeyboardButton(text=MainMenuButtons.HELP)],
    ]
    return ReplyKeyboardMarkup(
        keyboard=layout,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="🔘 لطفاً یکی از گزینه‌ها را انتخاب کن…",
    )
