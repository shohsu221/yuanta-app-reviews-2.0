"""
parse_reviews.py — turn the crawler's markdown tables into structured records.

Each *_App_Reviews.md file has a table:

    | 序號 | 時間 | 平台 | 用戶 | 評分 | 版本 | 評論標題與內容 |

Real pipes inside review text are escaped to the full-width '｜' by the crawler
(see review-crawler-agent/models.py), so a plain ' | ' split is safe. App Store
reviews prefix their title as ``**【title】** body``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

import pandas as pd

from config import APPS, ROOT

# A data row starts with "| <number> |"
_ROW_RE = re.compile(r"^\|\s*\d+\s*\|")
_RATING_RE = re.compile(r"\((\d)\)")
_TITLE_RE = re.compile(r"^\*\*【(.+?)】\*\*\s*(.*)$", re.DOTALL)


@dataclass
class Review:
    app: str           # app key (yuanta/cathay/sinopac)
    app_name: str
    platform: str      # "Google Play" | "App Store"
    date: Optional[str]  # ISO date "YYYY-MM-DD" (None if unparseable)
    month: Optional[str]  # "YYYY-MM"
    username: str
    rating: int        # 1-5 (0 if unknown)
    version: str
    title: Optional[str]
    content: str       # body only, title stripped out
    text: str          # title + content, for NLP


def _parse_rating(cell: str) -> int:
    m = _RATING_RE.search(cell)
    if m:
        return int(m.group(1))
    return cell.count("★")


def _parse_date(cell: str) -> tuple[Optional[str], Optional[str]]:
    cell = cell.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(cell, fmt)
            return dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m")
        except ValueError:
            continue
    return None, None


def _split_title(body: str) -> tuple[Optional[str], str]:
    m = _TITLE_RE.match(body.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, body.strip()


def parse_file(path, app_key: str, app_name: str) -> list[Review]:
    reviews: list[Review] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not _ROW_RE.match(line):
            continue
        # strip outer pipes, split into the 7 known columns
        inner = line.strip().strip("|")
        parts = [p.strip() for p in inner.split(" | ", 6)]
        if len(parts) != 7:
            continue
        _idx, dt_s, platform, user, rating_s, version, body = parts
        date, month = _parse_date(dt_s)
        title, content = _split_title(body)
        text = f"{title}。{content}" if title else content
        reviews.append(
            Review(
                app=app_key,
                app_name=app_name,
                platform=platform,
                date=date,
                month=month,
                username=user,
                rating=_parse_rating(rating_s),
                version=version,
                title=title,
                content=content,
                text=text,
            )
        )
    return reviews


def load_all(drop_low_value: bool = True) -> pd.DataFrame:
    """
    Parse all three apps into one tidy DataFrame.

    With ``drop_low_value`` (default), non-substantive reviews (bare 讚/好用/爛,
    emoji-only, too short …) are removed up front so every downstream metric —
    ratings, volume, trend, themes — is computed on specific reviews only. The
    raw vs kept counts are stashed on ``df.attrs`` for transparency.
    """
    rows: list[dict] = []
    for app in APPS:
        path = ROOT / app["file"]
        for r in parse_file(path, app["key"], app["name"]):
            rows.append(asdict(r))
    df = pd.DataFrame(rows)
    df["text"] = df["text"].fillna("").str.strip()
    df = df[df["text"].str.len() > 0].reset_index(drop=True)

    n_raw = len(df)
    n_dropped = 0
    if drop_low_value:
        from quality import is_low_value
        keep = ~df["text"].map(is_low_value)
        n_dropped = int((~keep).sum())
        df = df[keep].reset_index(drop=True)
    df.attrs["n_raw"] = n_raw
    df.attrs["n_dropped"] = n_dropped
    df.attrs["n_kept"] = len(df)
    return df


if __name__ == "__main__":
    df = load_all()
    print(f"Parsed {len(df)} reviews across {df['app'].nunique()} apps")
    print(df.groupby(["app_name", "platform"]).size())
    print("\nRating distribution:")
    print(df.groupby("app_name")["rating"].agg(["count", "mean"]).round(2))
    print("\nSample:")
    print(df[["app", "platform", "date", "rating", "version", "title"]].head(3).to_string())
