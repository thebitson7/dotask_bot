import re
import unicodedata
from typing import Iterable

# کاراکترهای فضای صفر-عرض و مشابه
_ZWSP = "\u200b\u200c\u200d\u2060\ufeff"

def normalize_text(s: str | None) -> str:
    if not s:
        return ""
    # نرمال‌سازی یونی‌کد، حذف فضاهای عجیب و فاصله‌های اضافی
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    s = s.translate({ord(ch): None for ch in _ZWSP})
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()

def matches_any(text: str | None, aliases: Iterable[str]) -> bool:
    t = normalize_text(text)
    return t in {normalize_text(a) for a in aliases}
