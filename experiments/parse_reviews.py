"""
parse_reviews.py — turn the crawler's JSON files into structured records.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

import pandas as pd

from config import APPS, ROOT


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


def load_app_reviews(app_key: str, app_name: str, file_prefix: str) -> list[Review]:
    """從該 App 的所有季度 JSON 檔案中載入評論。"""
    reviews: list[Review] = []
    comments_dir = ROOT / "data" / "comments"
    if not comments_dir.exists():
        return []

    for file in comments_dir.glob(f"{file_prefix}_*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    dt_tw = datetime.fromisoformat(item["date"])
                    date_s = dt_tw.strftime("%Y-%m-%d")
                    month_s = dt_tw.strftime("%Y-%m")

                    title = item.get("title")
                    content = item.get("content") or ""
                    text = f"{title}。{content}" if title else content

                    reviews.append(
                        Review(
                            app=app_key,
                            app_name=app_name,
                            platform=item["platform"],
                            date=date_s,
                            month=month_s,
                            username=item["username"],
                            rating=int(item["rating"]),
                            version=item["version"],
                            title=title,
                            content=content,
                            text=text,
                        )
                    )
        except Exception:
            pass
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
        for r in load_app_reviews(app["key"], app["name"], app["file_prefix"]):
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
