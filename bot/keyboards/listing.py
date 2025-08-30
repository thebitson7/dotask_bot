# bot/keyboards/listing.py
from __future__ import annotations

from math import ceil
from typing import Iterable
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.keyboards.priority import priority_label
from database.models import TaskPriority

# ─────────────────────────────────────────────────────────
# Callback schema (≤ 64 bytes):
#   هدر/ناوبری/فیلتر: tlist;s=o;p=1;f=A;d=A
#   اکشن تسک:         tact:<action>:<task_id>;s=o;p=1;f=A;d=A
#     action = done|undo|del|edit|snz
#   اسنوز انتخاب:     tsnz:<task_id>:<mins>;s=... (در هندلر)
#   noop:             noop or noop:listing
# ─────────────────────────────────────────────────────────

_PRIO_CYCLE = {"A": "H", "H": "M", "M": "L", "L": "A"}
_DATE_CYCLE = {"A": "T", "T": "W", "W": "O", "O": "N", "N": "A"}

_STATUS_LABEL = {"o": "📋 باز", "d": "✅ انجام‌شده"}
_DATE_LABEL = {
    "A": "📅 همهٔ تاریخ‌ها",
    "T": "📆 امروز",
    "W": "🗓 این هفته",
    "O": "⏰ گذشته",
    "N": "🚫 بدون تاریخ",
}

def _clamp_page(page: int, per_page: int, total: int) -> int:
    total_pages = max(1, ceil(max(0, total) / max(1, per_page)))
    return max(1, min(max(1, page), total_pages))

def _page_counter(page: int, per_page: int, total: int) -> str:
    total_pages = max(1, ceil(max(0, total) / max(1, per_page)))
    return f"صفحه {page}/{total_pages}"

def _join_kv(prefix: str, *, s: str, p: int, f: str, d: str) -> str:
    return f"{prefix};s={s};p={p};f={f};d={d}"

def _prio_cycle_label(next_f: str) -> str:
    mapping = {
        "A": "همهٔ اولویت‌ها",
        "H": priority_label(TaskPriority.HIGH, lang="fa"),
        "M": priority_label(TaskPriority.MEDIUM, lang="fa"),
        "L": priority_label(TaskPriority.LOW, lang="fa"),
    }
    return f"🎚 {mapping.get(next_f, 'همهٔ اولویت‌ها')}"

def _date_cycle_label(next_d: str) -> str:
    return _DATE_LABEL.get(next_d, _DATE_LABEL["A"])

def _status_label(s: str) -> str:
    return _STATUS_LABEL.get(s, _STATUS_LABEL["o"])

# ─────────────────────────────────────────────────────────
# هدر لیست: ناوبری + فیلترها + تازه‌سازی
# ─────────────────────────────────────────────────────────
def build_list_header_keyboard(
    *,
    status: str,
    page: int,
    per_page: int,
    total: int,
    prio_filter: str,
    date_filter: str,
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    page = _clamp_page(page, per_page, total)

    # ناوبری صفحه
    total_pages = max(1, ceil(max(0, total) / max(1, per_page)))
    prev_page = _clamp_page(page - 1, per_page, total)
    next_page = _clamp_page(page + 1, per_page, total)

    b.button(text="◀️ قبلی", callback_data=_join_kv("tlist", s=status, p=prev_page, f=prio_filter, d=date_filter))
    b.button(text=_page_counter(page, per_page, total), callback_data="noop:listing")
    b.button(text="بعدی ▶️", callback_data=_join_kv("tlist", s=status, p=next_page, f=prio_filter, d=date_filter))
    b.adjust(3)

    # وضعیت + چرخه اولویت + چرخه تاریخ
    toggle_s = "d" if status == "o" else "o"
    b.button(text=_status_label(toggle_s), callback_data=_join_kv("tlist", s=toggle_s, p=1, f=prio_filter, d=date_filter))

    next_f = _PRIO_CYCLE.get(prio_filter, "A")
    b.button(text=_prio_cycle_label(next_f), callback_data=_join_kv("tlist", s=status, p=1, f=next_f, d=date_filter))

    next_d = _DATE_CYCLE.get(date_filter, "A")
    b.button(text=_date_cycle_label(next_d), callback_data=_join_kv("tlist", s=status, p=1, f=prio_filter, d=next_d))
    b.adjust(3)

    # رفرش
    b.button(text="🔄 تازه‌سازی", callback_data=_join_kv("tlist", s=status, p=page, f=prio_filter, d=date_filter))
    b.adjust(1)

    return b.as_markup()

# ─────────────────────────────────────────────────────────
# کیبورد مخصوص هر کارت تسک (۴ اکشن)
# ─────────────────────────────────────────────────────────
def build_task_actions_keyboard(
    *,
    task_id: int,
    status: str,  # 'o' | 'd'
    page: int,
    prio_filter: str,
    date_filter: str,
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()

    # انجام/واگرد بسته به تب فعلی
    if status == "o":
        b.button(text="✅ انجام", callback_data=_join_kv(f"tact:done:{task_id}", s=status, p=page, f=prio_filter, d=date_filter))
    else:
        b.button(text="↩️ بازگرد", callback_data=_join_kv(f"tact:undo:{task_id}", s=status, p=page, f=prio_filter, d=date_filter))

    b.button(text="✏️ ویرایش", callback_data=_join_kv(f"tact:edit:{task_id}", s=status, p=page, f=prio_filter, d=date_filter))
    b.button(text="🗑 حذف",    callback_data=_join_kv(f"tact:del:{task_id}",  s=status, p=page, f=prio_filter, d=date_filter))
    b.button(text="🔁 اسنوز",  callback_data=_join_kv(f"tact:snz:{task_id}",  s=status, p=page, f=prio_filter, d=date_filter))
    b.adjust(4)

    return b.as_markup()
