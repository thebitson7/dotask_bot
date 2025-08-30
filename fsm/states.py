# fsm/states.py
from __future__ import annotations

from aiogram.fsm.state import StatesGroup, State

__all__ = [
    "AddTask",
    "EditTask",
    "SearchTask",
    "ViewTask",
]


class AddTask(StatesGroup):
    """
    🔧 جریان افزودن تسک جدید

    مراحل فعال فعلی:
      1) waiting_for_content     → دریافت متن تسک
      2) waiting_for_due_date    → انتخاب تاریخ (کلیدهای آماده)
      3) waiting_for_custom_date → ورود تاریخ دستی (اختیاری)
      4) waiting_for_priority    → انتخاب اولویت (HIGH/MEDIUM/LOW)

    نکات:
    - این نام‌ها در هندلرهای فعلی استفاده شده‌اند؛ تغییرشان سازگاری را می‌شکند.
    - برای آینده، می‌توان مراحل «پیش‌نمایش» یا «یادآور» را اضافه کرد.
    """

    # ✅ همین‌ها در کدهای فعلی استفاده می‌شوند — تغییر ندهید.
    waiting_for_content = State()
    waiting_for_due_date = State()
    waiting_for_custom_date = State()
    waiting_for_priority = State()

    # پیشنهادِ توسعه‌ی آینده (فعلاً استفاده نمی‌شود):
    # waiting_for_review = State()       # پیش‌نمایش قبل از ذخیره
    # waiting_for_reminder = State()     # تنظیم اعلان/یادآور
    # waiting_for_attachment = State()   # پیوست فایل/عکس


class EditTask(StatesGroup):
    """
    ✏️ جریان ویرایش متن تسک (نسخه‌ی ساده)
    - فقط یک مرحله: دریافت متن جدید و ثبت تغییر.
    - سازگار با هندلرهای فعلی (list_tasks.py).
    """
    waiting_for_new_content = State()


class SearchTask(StatesGroup):
    """
    🔎 جریان جستجوی تسک‌ها
    - UX بهتر: کاربر دکمه «جستجو» را می‌زند → وارد این جریان می‌شود.
    - پس از ارسال عبارت، نتایج به قالب «هاب لیست» نمایش داده می‌شود
      با دکمهٔ «❌ پاک‌کردن فیلتر» و امکان برگشت.

    حالت‌ها:
    - waiting_for_query: منتظر عبارت جستجو از کاربر
    - in_results: در صفحهٔ نتایج (با ناوبری/صفحه‌بندی همانند لیست)
    """
    waiting_for_query = State()
    in_results = State()


class ViewTask(StatesGroup):
    """
    🗂 نمای کارت جزئیات یک تسک
    - کارت تمیز با عنوان، موعد، اولویت، وضعیت و اکشن‌ها (✅/✏️/🔁/🗑/🔙)
    - در FSM فقط برای حفظ «کانتکستِ برگشت» نگه داشته می‌شود
      (مثلاً برگرداندن به همان صفحه/فیلتر قبلی در لیست).

    قرارداد داده‌های state (با state.update_data):
      - task_id: int               → شناسه تسکِ در حال نمایش
      - return_ctx: dict           → کانتکست ناوبری (s/p/f/d) برای برگشت
        مثلا: {"s":"o","p":2,"f":"H","d":"T"}

    حالت‌ها:
    - viewing: در حال نمایش کارت جزئیات
    """
    viewing = State()
