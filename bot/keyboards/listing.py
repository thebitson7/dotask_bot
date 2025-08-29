# bot/keyboards/listing.py
from __future__ import annotations

from math import ceil
from typing import Iterable, Optional, Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.priority import priority_label
from database.models import TaskPriority

# ─────────────────────────────────────────────────────────
# 📌 Callback schema (کوتاه و ≤ 64 بایت برای هر دکمه):
#   فهرست/ناوبری/فیلتر:  tlist;s=o;p=1;f=A;d=A
#     s: o=باز، d=انجام‌شده
#     p: شماره صفحه (۱-مبنا)
#     f: A/H/M/L  (همه/بالا/متوسط/پایین)
#     d: A/T/W/O/N (همه/امروز/این‌هفته/گذشته/بدون‌تاریخ)
#
#   اکشن روی تسک:       tact:<action>:<task_id>;s=o;p=1;f=A;d=A
#     action: done|undo|del|edit|snz
#
#   نادیده‌گرفتن کلیک:  noop:listing
# ─────────────────────────────────────────────────────────

# چرخه‌ی فیلتر اولویت و تاریخ
_PRIO_CYCLE = {"A": "H", "H": "M", "M": "L", "L": "A"}
_DATE_CYCLE = {"A": "T", "T": "W", "W": "O", "O": "N", "N": "A"}

# برچسب‌های فارسی وضعیت/تاریخ/اولویت
_STATUS_LABEL = {"o": "📋 باز", "d": "✅ انجام‌شده"}
_DATE_LABEL = {
    "A": "📅 همهٔ تاریخ‌ها",
    "T": "📆 امروز",
    "W": "🗓 این هفته",
    "O": "⏰ گذشته",
    "N": "🚫 بدون تاریخ",
}


def _clamp_page(page: int, per_page: int, total: int) -> int:
    """صفحه را در بازهٔ معتبر ۱..total_pages محدود می‌کند."""
    total_pages = max(1, ceil(max(0, total) / max(1, per_page)))
    return max(1, min(page, total_pages))


def _page_counter(page: int, per_page: int, total: int) -> str:
    total_pages = max(1, ceil(max(0, total) / max(1, per_page)))
    return f"صفحه {page}/{total_pages}"


def _join_kv(prefix: str, *, s: str, p: int, f: str, d: str) -> str:
    # ساخت callback_data فشرده و سازگار با محدودیت ۶۴ بایت
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


def build_listing_keyboard(
    *,
    task_ids: Iterable[int],
    status: str,        # 'o' (open) یا 'd' (done)
    page: int,
    per_page: int,
    total: int,
    prio_filter: str,   # 'A' | 'H' | 'M' | 'L'
    date_filter: str,   # 'A' | 'T' | 'W' | 'O' | 'N'
) -> InlineKeyboardMarkup:
    """
    ساخت کیبورد اینلاین لیست/ناوبری تسک‌ها با اکشن‌های ردیفی.

    نکات:
    - برای هر تسک ۴ اکشن می‌سازیم (انجام/واگرد، ویرایش، حذف، اسنوز).
    - ناوبری صفحه با قبلی/نمایش شمارنده/بعدی.
    - سه دکمهٔ فیلتر: تغییر وضعیت، چرخهٔ اولویت، چرخهٔ تاریخ.
    - دکمهٔ رفرش برای بازسازی همان صفحه با همان فیلترها.
    """
    b = InlineKeyboardBuilder()

    # نرمال‌سازی صفحه
    page = _clamp_page(page, per_page, total)

    # ردیف اکشن‌های هر تسک (۴ دکمه)
    for tid in task_ids:
        # انجام/واگرد
        if status == "o":
            b.button(
                text="✅",
                callback_data=_join_kv(f"tact:done:{tid}", s=status, p=page, f=prio_filter, d=date_filter),
            )
        else:
            b.button(
                text="↩️",
                callback_data=_join_kv(f"tact:undo:{tid}", s=status, p=page, f=prio_filter, d=date_filter),
            )

        # ویرایش / حذف / اسنوز
        b.button(
            text="✏️",
            callback_data=_join_kv(f"tact:edit:{tid}", s=status, p=page, f=prio_filter, d=date_filter),
        )
        b.button(
            text="🗑",
            callback_data=_join_kv(f"tact:del:{tid}", s=status, p=page, f=prio_filter, d=date_filter),
        )
        b.button(
            text="🔁",
            callback_data=_join_kv(f"tact:snz:{tid}", s=status, p=page, f=prio_filter, d=date_filter),
        )
        b.adjust(4)

    # ناوبری صفحه (قبلی/شمارنده/بعدی)
    total_pages = max(1, ceil(max(0, total) / max(1, per_page)))
    prev_page = _clamp_page(page - 1, per_page, total)
    next_page = _clamp_page(page + 1, per_page, total)

    b.button(text="◀️ قبلی", callback_data=_join_kv("tlist", s=status, p=prev_page, f=prio_filter, d=date_filter))
    # دکمهٔ وسط صرفاً نمایشی است (noop)
    b.button(text=_page_counter(page, per_page, total), callback_data="noop:listing")
    b.button(text="بعدی ▶️", callback_data=_join_kv("tlist", s=status, p=next_page, f=prio_filter, d=date_filter))
    b.adjust(3)

    # فیلترها + وضعیت (سوییچ وضعیت همیشه به صفحه ۱ می‌رود)
    toggle_s = "d" if status == "o" else "o"
    b.button(
        text=_status_label(toggle_s),
        callback_data=_join_kv("tlist", s=toggle_s, p=1, f=prio_filter, d=date_filter),
    )

    # چرخه‌ی اولویت: A→H→M→L→A (نمایش لیبل وضعیت بعدی برای شفافیت)
    next_f = _PRIO_CYCLE.get(prio_filter, "A")
    b.button(
        text=_prio_cycle_label(next_f),
        callback_data=_join_kv("tlist", s=status, p=1, f=next_f, d=date_filter),
    )

    # چرخه‌ی تاریخ: A→T→W→O→N→A
    next_d = _DATE_CYCLE.get(date_filter, "A")
    b.button(
        text=_date_cycle_label(next_d),
        callback_data=_join_kv("tlist", s=status, p=1, f=prio_filter, d=next_d),
    )
    b.adjust(3)

    # رفرش
    b.button(
        text="🔄 تازه‌سازی",
        callback_data=_join_kv("tlist", s=status, p=page, f=prio_filter, d=date_filter),
    )
    b.adjust(1)

    return b.as_markup()
