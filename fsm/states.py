from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.state import StatesGroup, State

class AddTask(StatesGroup):
    """
    💼 وضعیت‌های مربوط به فرآیند افزودن تسک جدید در ربات.

    مراحل فعال:
    1️⃣ دریافت محتوای تسک
    2️⃣ انتخاب تاریخ (از بین گزینه‌ها)
    3️⃣ ورود تاریخ دلخواه توسط کاربر (در صورت نیاز)
    4️⃣ انتخاب اولویت تسک (کم، متوسط، زیاد)

    💡 توسعه‌پذیری آینده:
    - 🔔 افزودن یادآوری (reminder)
    - 📝 پیش‌نمایش و ویرایش قبل از ذخیره
    - 📎 افزودن فایل یا عکس مرتبط به تسک
    """

    waiting_for_content = State()         # ➤ مرحله 1: دریافت محتوای تسک از کاربر
    waiting_for_due_date = State()        # ➤ مرحله 2: انتخاب تاریخ از بین گزینه‌ها
    waiting_for_custom_date = State()     # ➤ مرحله 3: ورود تاریخ دلخواه (اختیاری)
    waiting_for_priority = State()        # ➤ مرحله 4: انتخاب اولویت (low / medium / high)

    # آماده برای توسعه بعدی:
    # waiting_for_reminder = State()     # 🔔 فعال‌سازی یادآوری زمان‌دار
    # waiting_for_attachment = State()   # 📎 بارگذاری فایل یا عکس به همراه تسک
# fsm/states.py  (افزودن کنار AddTask)


class EditTask(StatesGroup):
    waiting_for_new_content = State()
