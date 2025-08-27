from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
import logging

from fsm.states import AddTask
from database.session import get_session
from database.crud import create_or_update_user, create_task
from bot.keyboards.main_menu import main_menu_keyboard
from bot.keyboards.priority import priority_keyboard
from database.models import TaskPriority

router = Router()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 🎯 مرحله 1: شروع افزودن تسک
# ─────────────────────────────────────────────
@router.message(F.text == "➕ افزودن تسک")
async def start_add_task(message: Message, state: FSMContext):
    logger.info(f"[➕ ADD TASK] User {message.from_user.id} started task creation.")

    # ✅ اطمینان از وجود کاربر
    async with get_session() as session:
        await create_or_update_user(
            session=session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
            language=message.from_user.language_code or "fa"
        )

    await message.answer(
        "📝 لطفاً محتوای تسک رو وارد کن (مثلاً: خرید نان):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AddTask.waiting_for_content)


# ─────────────────────────────────────────────
# ✍️ مرحله 2: دریافت محتوای تسک
# ─────────────────────────────────────────────
@router.message(AddTask.waiting_for_content, F.text)
async def receive_content(message: Message, state: FSMContext):
    content = message.text.strip()

    if len(content) < 3:
        await message.answer("❗ محتوای تسک خیلی کوتاهه. لطفاً حداقل ۳ کاراکتر وارد کن.")
        return

    await state.update_data(content=content)
    await state.set_state(AddTask.waiting_for_due_date)

    await message.answer("⏰ زمان انجام تسک رو انتخاب کن:", reply_markup=_build_due_date_keyboard())


# ─────────────────────────────────────────────
# ⏰ مرحله 3: انتخاب تاریخ از گزینه‌ها
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("due:"))
async def handle_due_selection(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":")[1]
    now = datetime.now()
    due_date = None

    match choice:
        case "today": due_date = now
        case "tomorrow": due_date = now + timedelta(days=1)
        case "urgent": due_date = now + timedelta(hours=2)
        case "week": due_date = now + timedelta(days=(6 - now.weekday()))
        case "none": due_date = None
        case "manual":
            await callback.message.answer("📅 تاریخ دلخواه رو وارد کن (فرمت: YYYY-MM-DD):")
            await state.set_state(AddTask.waiting_for_custom_date)
            await callback.answer()
            return
        case _:
            logger.warning(f"[⚠️ INVALID DATE SELECTED] user={callback.from_user.id} -> {choice}")
            await callback.answer("❗ انتخاب تاریخ نامعتبر بود.")
            return

    await state.update_data(due_date=due_date)
    await state.set_state(AddTask.waiting_for_priority)
    await callback.message.answer("📌 لطفاً اولویت تسک رو انتخاب کن:", reply_markup=priority_keyboard())
    await callback.answer()


# ─────────────────────────────────────────────
# 🗓 مرحله 3.5: دریافت تاریخ دستی
# ─────────────────────────────────────────────
@router.message(AddTask.waiting_for_custom_date, F.text)
async def receive_custom_date(message: Message, state: FSMContext):
    try:
        due_date = datetime.strptime(message.text.strip(), "%Y-%m-%d")
        if due_date < datetime.now():
            await message.answer("⚠️ تاریخ وارد شده گذشته‌ست. لطفاً تاریخ آینده وارد کن.")
            return
        await state.update_data(due_date=due_date)
    except ValueError:
        await message.answer("❗ فرمت اشتباهه. مثال: 2025-09-15")
        return

    await state.set_state(AddTask.waiting_for_priority)
    await message.answer("📌 حالا لطفاً اولویت تسک رو انتخاب کن:", reply_markup=priority_keyboard())


# ─────────────────────────────────────────────
# 🚦 مرحله 4: انتخاب اولویت تسک
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("priority:"))
async def handle_priority_selection(callback: CallbackQuery, state: FSMContext):
    raw_priority = callback.data.split(":")[1].upper()

    try:
        priority = TaskPriority[raw_priority]
    except KeyError:
        logger.warning(f"[❗ INVALID PRIORITY] user={callback.from_user.id}, data={raw_priority}")
        await callback.answer("❗ اولویت نامعتبره.")
        return

    await state.update_data(priority=priority.name)
    await callback.answer()
    await save_task(callback, state)


# ─────────────────────────────────────────────
# 💾 مرحله 5: ذخیره‌سازی تسک
# ─────────────────────────────────────────────
async def save_task(source: Message | CallbackQuery, state: FSMContext):
    user_info = source.from_user
    data = await state.get_data()

    content = data.get("content")
    due_date = data.get("due_date")
    priority_str = data.get("priority")

    try:
        priority = TaskPriority[priority_str.upper()]
    except (KeyError, AttributeError):
        logger.warning(f"[❗ INVALID PRIORITY FALLBACK] user={user_info.id}, raw={priority_str}")
        priority = TaskPriority.MEDIUM

    if not content:
        await send_message(source, "❗ خطا در دریافت محتوای تسک. مجدد تلاش کن.")
        await state.clear()
        return

    async with get_session() as session:
        user = await create_or_update_user(
            session=session,
            telegram_id=user_info.id,
            full_name=user_info.full_name,
            username=user_info.username,
            language=user_info.language_code or "fa"
        )

        if not user:
            logger.error(f"[❌ USER NOT FOUND] while saving task for telegram_id={user_info.id}")
            await send_message(source, "❗ حساب کاربری پیدا نشد. لطفاً /start رو بزن.")
            await state.clear()
            return

        task = await create_task(
            session=session,
            user_id=user.id,
            content=content,
            due_date=due_date,
            priority=priority
        )

        if task:
            await send_message(source, "✅ تسک با موفقیت ثبت شد!")
            logger.info(f"[📌 TASK CREATED] user_id={user_info.id}, task_id={task.id}")
        else:
            logger.error(f"[❌ TASK CREATION FAILED] user_id={user_info.id}")
            await send_message(source, "❌ ذخیره تسک ناموفق بود.")

    await state.clear()
    await send_message(source, "🏠 برگشت به منوی اصلی:", reply_markup=main_menu_keyboard())


# ─────────────────────────────────────────────
# 🧠 Helper: ارسال پیام بسته به نوع منبع
# ─────────────────────────────────────────────
async def send_message(source: Message | CallbackQuery, text: str, **kwargs):
    try:
        if isinstance(source, Message):
            await source.answer(text, **kwargs)
        elif isinstance(source, CallbackQuery):
            await source.message.answer(text, **kwargs)
    except Exception as e:
        logger.warning(f"[⚠️ FAILED TO SEND MESSAGE] user={source.from_user.id} -> {e}")


# ─────────────────────────────────────────────
# 🧰 Helper: کیبورد تاریخ‌ها
# ─────────────────────────────────────────────
def _build_due_date_keyboard():
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📅 امروز", "due:today"),
        ("🕒 فردا", "due:tomorrow"),
        ("🔥 فوری (۲ ساعت آینده)", "due:urgent"),
        ("🗓 تا آخر هفته", "due:week"),
        ("❌ بدون تاریخ", "due:none"),
        ("✍️ تاریخ دلخواه", "due:manual"),
    ]
    for text, data in buttons:
        builder.button(text=text, callback_data=data)
    builder.adjust(2)
    return builder.as_markup()
