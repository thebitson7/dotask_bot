# fsm/states.py

from aiogram.fsm.state import StatesGroup, State

class AddTask(StatesGroup):
    """
    💼 FSM برای افزودن تسک جدید به ربات.
    
    مراحل:
    1️⃣ دریافت محتوای تسک از کاربر
    2️⃣ دریافت انتخاب تاریخ (از دکمه‌ها)
    3️⃣ ورود تاریخ دستی (در صورت انتخاب کاربر)

    قابلیت توسعه در آینده:
    - 🎯 تعیین اولویت (priority)
    - 🔔 افزودن یادآوری (reminder)
    - 📝 ویرایش قبل از ذخیره
    """

    waiting_for_content = State()         # ➤ منتظر دریافت محتوای تسک
    waiting_for_due_date = State()        # ➤ منتظر انتخاب تاریخ از بین دکمه‌ها
    waiting_for_custom_date = State()     # ➤ منتظر وارد کردن تاریخ دستی (اختیاری)
