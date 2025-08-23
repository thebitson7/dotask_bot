# fsm/states.py

from aiogram.fsm.state import StatesGroup, State

class AddTask(StatesGroup):
    """
    💼 FSM برای افزودن تسک جدید به ربات.
    
    مراحل:
    1️⃣ دریافت محتوای تسک از کاربر
    2️⃣ دریافت تاریخ سررسید (یا «ندارم»)

    قابل گسترش برای:
    - تعیین اولویت (priority)
    - افزودن یادآوری (reminder)
    - ویرایش یا حذف قبل از ذخیره
    """

    waiting_for_content = State()    # ➤ منتظر دریافت محتوای تسک
    waiting_for_due_date = State()   # ➤ منتظر دریافت تاریخ سررسید
