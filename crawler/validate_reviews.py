"""
validate_reviews.py — review data integrity checks for crawler output.
"""
import re
import json
from collections import Counter
from pathlib import Path
from typing import Optional
from datetime import datetime

import config


def _iter_review_keys(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for r in data:
        title = r.get("title")
        content = r.get("content") or ""
        if title:
            text = f"**【{title}】** {content}"
        else:
            text = content
        
        # 標題與內文正規化
        norm_text = re.sub(r"\*\*【(.+?)】\*\*", r"【\1】", text)
        norm_text = norm_text.replace("|", "｜").strip()
        norm_text = re.sub(r"\s+", " ", norm_text).casefold()
        
        # 使用日期 (YYYY-MM-DD) 作為唯一鍵的一部分，允許在不同日期發表相同評論
        date_s = datetime.fromisoformat(r["date"]).strftime("%Y-%m-%d")
        yield (r["platform"], r["username"].strip().casefold(), str(r["rating"]), norm_text, date_s)


def validate_no_duplicate_reviews() -> None:
    """Raise ValueError if any JSON review file contains duplicate review content."""
    comments_dir = Path(config.COMMENTS_DIR)
    if not comments_dir.exists():
        return

    errors = []
    for file_path in comments_dir.glob("*.json"):
        keys = list(_iter_review_keys(file_path))
        counts = Counter(keys)
        duplicates = [(key, count) for key, count in counts.items() if count > 1]
        if duplicates:
            sample = "; ".join(
                f"{key[0]} / {key[1]} / {key[2]}★ x{count}"
                for key, count in duplicates[:5]
            )
            errors.append(f"{file_path.name}: {len(duplicates)} duplicate groups ({sample})")

    if errors:
        raise ValueError("Review duplicate validation failed: " + " | ".join(errors))


if __name__ == "__main__":
    validate_no_duplicate_reviews()
    print("Review duplicate validation passed.")
