from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from datetime import datetime

from fsm.states import AddTask
from database.session import get_session
from database.crud import get_user_by_telegram_id, create_task

from bot.keyboards.main_menu import main_menu_keyboard

import logging
logger = logging.getLogger(__name__)

router = Router()


# ─────────────────────────────
# مرحله 1: شروع افزودن تسک
# ─────────────────────────────
@router.message(F.text == "➕ افزودن تسک")
async def start_add_task(message: Message, state: FSMContext):
    await message.answer(
        "📝 لطفاً محتوای تسک را وارد کن (مثلاً: خرید نان):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AddTask.waiting_for_content)
    logger.info(f"[➕ ADD_TASK] User {message.from_user.id} -> وارد مرحله محتوا شد.")


# ─────────────────────────────
# مرحله 2: وارد کردن محتوا
# ─────────────────────────────
@router.message(AddTask.waiting_for_content, F.text)
async def process_content(message: Message, state: FSMContext):
    content = message.text.strip()

    if not content:
        await message.answer("❗ لطفاً محتوای تسک را وارد کن.")
        return

    await state.update_data(content=content)
    await message.answer("📅 تاریخ سررسید را وارد کن (مثلاً 1403-01-15) یا بنویس «ندارم»:")
    await state.set_state(AddTask.waiting_for_due_date)


# ─────────────────────────────
# مرحله 3: ذخیره‌سازی
# ─────────────────────────────
@router.message(AddTask.waiting_for_due_date, F.text)
async def process_due_date(message: Message, state: FSMContext):
    due_date_text = message.text.strip()
    user_id = message.from_user.id

    if due_date_text.lower() in ["ندارم", "nadarom", "نداروم"]:
        due_date = None
    else:
        try:
            due_date = datetime.strptime(due_date_text, "%Y-%m-%d")
        except ValueError:
            await message.answer("❌ فرمت تاریخ اشتباهه. لطفاً مثل «1403-01-15» وارد کن یا بنویس «ندارم».")
            return

    data = await state.get_data()
    content = data.get("content")

    async with get_session() as session:
        db_user = await get_user_by_telegram_id(session, telegram_id=user_id)
        if not db_user:
            await message.answer("❗ مشکلی در شناسایی شما پیش آمد.")
            await state.clear()
            return

        task = await create_task(
            session=session,
            user_id=db_user.id,
            content=content,
            due_date=due_date
        )

        if task:
            await message.answer("✅ تسک با موفقیت ذخیره شد! 🎉")
        else:
            await message.answer("⚠️ مشکلی در ذخیره تسک پیش آمد.")

    await state.clear()

    # نمایش مجدد منوی اصلی
    await message.answer("🔙 برگشت به منوی اصلی:", reply_markup=main_menu_keyboard())
