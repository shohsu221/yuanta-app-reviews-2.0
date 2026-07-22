"""
quality.py — drop non-substantive reviews before analysis.

A review is treated as *low-value* (carries no actionable information) when it is:
  * a bare generic verdict        — 讚 / 好用 / 爛 / good / ok …
  * emoji / punctuation only      — 👍👍👍 、！！！
  * too short to be specific      — < MIN_LEN CJK chars / latin words
  * empty of content tokens       — nothing left after jieba + stopword removal

Concrete short reviews are deliberately KEPT (e.g. 字體太小、畫面不能截圖、
以前很好用現在卡卡), because they name a real, fixable issue. Tune the lists /
MIN_LEN below to make filtering stricter or looser.
"""
from __future__ import annotations

import re

from text_zh import tokenize

# bare verdicts with no detail (compared after stripping punctuation/digits)
GENERIC = {
    "好用", "很好用", "好用喔", "讚", "讚讚", "很讚", "超讚", "讚啦", "好評", "給讚",
    "爛", "很爛", "爛死了", "垃圾", "雷", "不錯", "還不錯", "很好", "普通", "還好",
    "棒", "很棒", "超棒", "讚喔", "便捷", "便利", "夠正", "好", "差", "可以", "尚可",
    "如題", "如內文", "無", "沒有", "test", "ok", "okok", "good", "nice", "great",
    "讚啦讚啦", "好用推", "推", "推薦", "神", "猛",
}

MIN_LEN = 4  # minimum CJK chars / latin words to count as "specific"

_LEN_RE = re.compile(r"[一-鿿]|[A-Za-z]+")
_EMOJI_ONLY = re.compile(r"^[\U0001F000-\U0001FAFF☀-➿\s。，、！？!?.,~\-_]+$")
_STRIP = re.compile(r"[\s。，、！？!?.,~\-_0-9]+")


def content_len(text: str) -> int:
    """Number of CJK characters + latin words (ignores punctuation/digits)."""
    return len(_LEN_RE.findall(str(text)))


def is_low_value(text: str) -> bool:
    t = str(text).strip()
    if not t:
        return True
    if _EMOJI_ONLY.match(t):
        return True
    if _STRIP.sub("", t).lower() in GENERIC:
        return True
    if content_len(t) < MIN_LEN:
        return True
    if len(tokenize(t)) == 0:
        return True
    return False


if __name__ == "__main__":
    samples = ["讚", "good 👍", "👍👍👍", "字體太小", "畫面不能截圖",
               "以前很好用，現在開都會卡卡的", "又當機", "除權息資料一直重新載入點進去還是黑的"]
    for s in samples:
        print(f"{'DROP' if is_low_value(s) else 'KEEP'}  {s}")
