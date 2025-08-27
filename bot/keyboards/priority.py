from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import TaskPriority


def priority_keyboard() -> InlineKeyboardMarkup:
    """
    🎛️ کیبورد اینلاین برای انتخاب اولویت تسک
    
    🔴 بالا (HIGH)
    🟡 متوسط (MEDIUM)
    🟢 پایین (LOW)
    """
    priority_labels = {
        TaskPriority.HIGH.name: "🔴 بالا",
        TaskPriority.MEDIUM.name: "🟡 متوسط",
        TaskPriority.LOW.name: "🟢 پایین",
    }

    builder = InlineKeyboardBuilder()

    for priority_name, label in priority_labels.items():
        builder.button(
            text=label,
            callback_data=f"priority:{priority_name}"
        )

    builder.adjust(3)
    return builder.as_markup()
