from aiogram import Router, F
from aiogram.types import Message
import logging

from bot.keyboards.main_menu import (
    main_menu_keyboard,
    ADD_TASK_ALIASES,
    LIST_TASKS_ALIASES,
    SETTINGS_ALIASES,
    HELP_ALIASES,
)
from bot.utils.text_match import matches_any, normalize_text

from database.session import get_session
from database.crud import get_tasks_by_user_id, create_or_update_user

router = Router()
logger = logging.getLogger(__name__)

async def _ensure_user_id(tg_user) -> int | None:
    try:
        async with get_session() as session:
            u = await create_or_update_user(
                session=session,
                telegram_id=tg_user.id,
                full_name=tg_user.full_name,
                username=tg_user.username,
                language=tg_user.language_code or "fa",
            )
            return u.id if u else None
    except Exception as e:
        logger.exception(f"[menu] ensure_user failed tg={tg_user.id} -> {e}")
        return None

# ————— add task —————
@router.message(F.text.func(lambda t: matches_any(t, ADD_TASK_ALIASES)))
async def on_add_task(message: Message):
    logger.info(f"[menu] AddTask clicked by {message.from_user.id} -> text='{normalize_text(message.text)}'")
    # اینجا یا وارد FSM اضافه‌کردن تسک شو، یا فعلاً پیام راهنما بده
    await message.answer(
        "➕ ایجاد تسک جدید:\n"
        "متن تسک و (اختیاری) تاریخ را بفرست.\n"
        "مثال: «خرید شیر فردا ساعت ۹»",
        reply_markup=main_menu_keyboard()
    )

# ————— list tasks —————
@router.message(F.text.func(lambda t: matches_any(t, LIST_TASKS_ALIASES)))
async def on_list_tasks(message: Message):
    user = message.from_user
    logger.info(f"[menu] ListTasks clicked by {user.id} -> text='{normalize_text(message.text)}'")
    uid = await _ensure_user_id(user)
    if not uid:
        await message.answer("❗ حساب شما شناسایی نشد. /start را بزنید.", reply_markup=main_menu_keyboard())
        return

    # دریافت تسک‌ها
    try:
        async with get_session() as session:
            tasks = await get_tasks_by_user_id(session, user_id=uid)
    except Exception as e:
        logger.exception(f"[menu] get_tasks_by_user_id failed uid={uid} -> {e}")
        await message.answer("⚠️ خطا در دریافت لیست وظایف.", reply_markup=main_menu_keyboard())
        return

    if not tasks:
        await message.answer("📭 هنوز هیچ تسکی ثبت نکردی.", reply_markup=main_menu_keyboard())
        return

    # ارسال خلاصه + پیشنهاد فیلتر
    lines = []
    for i, t in enumerate(tasks, start=1):
        due = t.due_date.strftime("%Y-%m-%d %H:%M") if t.due_date else "—"
        status = "✅" if t.is_done else "🕒"
        lines.append(f"{i}. {t.content} | {status} | ⏰ {due}")
    await message.answer("📋 لیست وظایف:\n" + "\n".join(lines), reply_markup=main_menu_keyboard())

# ————— settings —————
@router.message(F.text.func(lambda t: matches_any(t, SETTINGS_ALIASES)))
async def on_settings(message: Message):
    logger.info(f"[menu] Settings clicked by {message.from_user.id}")
    await message.answer("⚙️ تنظیمات به‌زودی…", reply_markup=main_menu_keyboard())

# ————— help —————
@router.message(F.text.func(lambda t: matches_any(t, HELP_ALIASES)))
async def on_help(message: Message):
    logger.info(f"[menu] Help clicked by {message.from_user.id}")
    await message.answer(
        "ℹ️ راهنما:\n"
        "➕ افزودن تسک: یک تسک جدید بساز.\n"
        "📋 لیست وظایف: تسک‌های ثبت‌شده را ببین.\n",
        reply_markup=main_menu_keyboard()
    )

# ————— لاگِ پیام‌های unmatched برای عیب‌یابی —————
@router.message(F.text)
async def on_any_text(message: Message):
    # اگر هیچ کدام match نشد، اینجا لاگ کن تا بفهمیم متن دقیقا چی بوده
    logger.debug(f"[menu] Unmatched text from {message.from_user.id}: {repr(message.text)} (norm={normalize_text(message.text)!r})")
