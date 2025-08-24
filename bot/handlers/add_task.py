# bot/handlers/add_task.py

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from datetime import datetime
import logging

from fsm.states import AddTask
from database.session import get_session
from database.crud import get_user_by_telegram_id, create_task
from bot.keyboards.main_menu import main_menu_keyboard

router = Router()
logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────
# 🎯 مرحله 1: شروع افزودن تسک
# ────────────────────────────────────────────────
@router.message(F.text == "➕ افزودن تسک")
async def start_add_task(message: Message, state: FSMContext):
    """
    مرحله آغاز افزودن تسک - درخواست محتوای تسک از کاربر
    """
    logger.info(f"[➕ START] User {message.from_user.id} وارد افزودن تسک شد.")
    await message.answer(
        "📝 لطفاً محتوای تسک رو وارد کن (مثلاً: خرید نان):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AddTask.waiting_for_content)


# ────────────────────────────────────────────────
# ✍️ مرحله 2: دریافت محتوای تسک
# ────────────────────────────────────────────────
@router.message(AddTask.waiting_for_content, F.text)
async def receive_content(message: Message, state: FSMContext):
    """
    دریافت و اعتبارسنجی محتوای تسک
    """
    content = message.text.strip()

    if not content or len(content) < 2:
        await message.answer("❗ محتوای تسک خیلی کوتاهه یا معتبر نیست. لطفاً دوباره وارد کن.")
        return

    await state.update_data(content=content)
    await state.set_state(AddTask.waiting_for_due_date)
    await message.answer("📅 تاریخ سررسید رو وارد کن (مثلاً 1403-01-15) یا بنویس «ندارم»:")
    logger.info(f"[📝 CONTENT] User {message.from_user.id} وارد مرحله تاریخ شد.")


# ────────────────────────────────────────────────
# ⏰ مرحله 3: دریافت تاریخ و ذخیره‌سازی تسک
# ────────────────────────────────────────────────
@router.message(AddTask.waiting_for_due_date, F.text)
async def receive_due_date(message: Message, state: FSMContext):
    """
    دریافت تاریخ سررسید (اختیاری) و ذخیره تسک در دیتابیس
    """
    user_id = message.from_user.id
    due_date_text = message.text.strip()
    due_date = None

    # 📆 اعتبارسنجی تاریخ
    if due_date_text.lower() not in ["ندارم", "nadarom", "نداروم"]:
        try:
            due_date = datetime.strptime(due_date_text, "%Y-%m-%d")
        except ValueError:
            await message.answer("❌ فرمت تاریخ اشتباهه. لطفاً به صورت «1403-01-15» وارد کن یا بنویس «ندارم».")
            return

    data = await state.get_data()
    content = data.get("content")

    if not content:
        logger.warning(f"[⚠️ MISSING CONTENT] User {user_id} بدون محتوا به مرحله تاریخ رسید.")
        await message.answer("❗ مشکلی پیش اومد. لطفاً دوباره شروع کن.")
        await state.clear()
        return

    async with get_session() as session:
        db_user = await get_user_by_telegram_id(session, telegram_id=user_id)

        if not db_user:
            logger.warning(f"[❌ USER NOT FOUND] telegram_id={user_id}")
            await message.answer("⚠️ کاربر شناسایی نشد. لطفاً /start رو بزن.")
            await state.clear()
            return

        task = await create_task(session, user_id=db_user.id, content=content, due_date=due_date)

        if task:
            logger.info(f"[✅ TASK CREATED] user={user_id} -> task_id={task.id}")
            await message.answer("✅ تسک با موفقیت ذخیره شد! 🎉")
        else:
            logger.error(f"[💥 FAILED TO CREATE TASK] user={user_id}")
            await message.answer("❗ مشکلی در ذخیره تسک پیش اومد. لطفاً دوباره امتحان کن.")

    await state.clear()
    await message.answer("🔙 برگشت به منوی اصلی:", reply_markup=main_menu_keyboard())
