"""
text_zh.py — Traditional-Chinese tokenisation for scikit-learn vectorisers.

scikit-learn's default analyzer splits on whitespace/punctuation, which fails on
Chinese (no spaces). We tokenise with jieba, load a domain user-dictionary so
trading terms (停損單, 複委託, 零股 …) stay intact, then drop stopwords, pure
punctuation and pure-digit tokens. The result is a callable usable directly as
``TfidfVectorizer(tokenizer=tokenize, ...)``.
"""
from __future__ import annotations

import re
from functools import lru_cache

import jieba

from config import STOPWORDS_FILE, USERDICT_FILE

# Keep CJK ideographs and latin words; drop everything else.
_TOKEN_OK = re.compile(r"^[一-鿿A-Za-z][一-鿿A-Za-z]*$")
_DIGITS = re.compile(r"^\d+$")


@lru_cache(maxsize=1)
def _stopwords() -> frozenset[str]:
    words = set()
    if STOPWORDS_FILE.exists():
        for line in STOPWORDS_FILE.read_text(encoding="utf-8").splitlines():
            w = line.strip()
            if w:
                words.add(w)
    return frozenset(words)


@lru_cache(maxsize=1)
def _ensure_userdict() -> bool:
    if USERDICT_FILE.exists():
        jieba.load_userdict(str(USERDICT_FILE))
    # quieten jieba's first-run logging
    jieba.setLogLevel(60)
    return True


def tokenize(text: str) -> list[str]:
    """Tokenise one review into meaningful Chinese/Latin terms."""
    _ensure_userdict()
    stop = _stopwords()
    out: list[str] = []
    for tok in jieba.cut(str(text), cut_all=False):
        tok = tok.strip().lower()
        if not tok or _DIGITS.match(tok):
            continue
        if tok in stop:
            continue
        # keep latin words of len>=2, and chinese tokens of len>=2
        # (single chinese chars are usually too generic to be a "theme")
        if len(tok) < 2:
            continue
        if not _TOKEN_OK.match(tok):
            continue
        out.append(tok)
    return out


def tokenized_join(text: str) -> str:
    """Space-joined tokens (handy for wordclouds / debugging)."""
    return " ".join(tokenize(text))


if __name__ == "__main__":
    samples = [
        "期貨連停損單設定都沒有是怎樣包一包回家啦！",
        "每次開盤都要等很久才能進去掛 進到那個頁面一直都是處理中 能進去的時候很常都已經開始走低 爛死了",
        "庫存頁面改善，希望能用紅色綠色來標示市價，使用者便可以一目了然",
        "史上最棒的證券app！",
    ]
    for s in samples:
        print(s)
        print("  ->", tokenize(s))
