# ✅ version: patched & localized

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from aiogram.utils.keyboard import InlineKeyboardBuilder
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
    logger.info(f"[➕ افزودن تسک] کاربر {message.from_user.id} وارد مرحله افزودن شد.")
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
    content = message.text.strip()
    if not content or len(content) < 2:
        await message.answer("❗ محتوای تسک خیلی کوتاهه یا معتبر نیست. لطفاً دوباره وارد کن.")
        return

    await state.update_data(content=content)
    await state.set_state(AddTask.waiting_for_due_date)

    # 🎛️ دکمه‌های انتخاب تاریخ
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 امروز", callback_data="due:today")
    builder.button(text="🕒 فردا", callback_data="due:tomorrow")
    builder.button(text="🔥 فوری (۲ ساعت آینده)", callback_data="due:urgent")
    builder.button(text="🗓 تا آخر هفته", callback_data="due:week")
    builder.button(text="❌ بدون تاریخ", callback_data="due:none")
    builder.button(text="✍️ تاریخ دلخواه", callback_data="due:manual")
    builder.adjust(2)

    await message.answer("⏰ زمان انجام تسک رو انتخاب کن:", reply_markup=builder.as_markup())


# ────────────────────────────────────────────────
# ⏰ انتخاب سریع تاریخ
# ────────────────────────────────────────────────
@router.callback_query(F.data.startswith("due:"))
async def handle_due_selection(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":")[1]
    now = datetime.now()
    due_date = None

    match choice:
        case "today": due_date = now
        case "tomorrow": due_date = now + timedelta(days=1)
        case "urgent": due_date = now + timedelta(hours=2)
        case "week": due_date = now + timedelta(days=3)
        case "none": due_date = None
        case "manual":
            await callback.message.answer("📅 لطفاً تاریخ دلخواه رو وارد کن (مثلاً 2025-09-15):")
            await state.set_state(AddTask.waiting_for_custom_date)
            await callback.answer()
            return
        case _: 
            await callback.answer("❌ انتخاب نامعتبر بود.")
            return

    await callback.answer()
    await create_and_save_task(callback, state, due_date)


# ────────────────────────────────────────────────
# ✍️ تاریخ دستی وارد شده توسط کاربر
# ────────────────────────────────────────────────
@router.message(AddTask.waiting_for_custom_date, F.text)
async def receive_custom_date(message: Message, state: FSMContext):
    try:
        due_date = datetime.strptime(message.text.strip(), "%Y-%m-%d")
    except ValueError:
        await message.answer("❗ فرمت تاریخ اشتباهه. لطفاً به صورت 2025-09-15 وارد کن.")
        return

    await create_and_save_task(message, state, due_date)


# ────────────────────────────────────────────────
# 💾 ذخیره تسک
# ────────────────────────────────────────────────
async def create_and_save_task(source, state: FSMContext, due_date: datetime | None):
    user_id = source.from_user.id
    data = await state.get_data()
    content = data.get("content")

    if not content:
        await send_message(source, "❗ مشکلی پیش اومد. لطفاً دوباره شروع کن.")
        await state.clear()
        return

    async with get_session() as session:
        db_user = await get_user_by_telegram_id(session, telegram_id=user_id)

        if not db_user:
            await send_message(source, "❗ کاربر شناسایی نشد. لطفاً /start رو بزن.")
            await state.clear()
            return

        task = await create_task(session, user_id=db_user.id, content=content, due_date=due_date)

        if task:
            await send_message(source, "✅ تسک با موفقیت ذخیره شد!")
        else:
            await send_message(source, "❗ مشکلی در ذخیره تسک پیش اومد.")

    await state.clear()
    await send_message(source, "🔙 برگشت به منوی اصلی:", reply_markup=main_menu_keyboard())


# ────────────────────────────────────────────────
# 🧠 helper برای پاسخ مناسب
# ────────────────────────────────────────────────
async def send_message(source, text: str, **kwargs):
    """
    به درستی بین message و callback فرق می‌گذارد.
    """
    if isinstance(source, Message):
        await source.answer(text, **kwargs)
    elif isinstance(source, CallbackQuery):
        await source.message.answer(text, **kwargs)
