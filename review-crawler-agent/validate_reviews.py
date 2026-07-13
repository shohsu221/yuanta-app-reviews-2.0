"""
validate_reviews.py — review data integrity checks for crawler output.
"""
import re
from collections import Counter
from pathlib import Path
from typing import Optional

import config


_ROW_RE = re.compile(r"^\|\s*\d+\s*\|")


def _normalize_review_text(text: str) -> str:
    text = re.sub(r"\*\*【(.+?)】\*\*", r"【\1】", text)
    text = text.replace("|", "｜").strip()
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


def _iter_review_keys(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if not _ROW_RE.match(line):
            continue

        parts = line.split("|")
        if len(parts) < 8:
            continue

        rating_match = re.search(r"\((\d)\)", parts[5])
        if not rating_match:
            continue

        platform = parts[3].strip()
        username = parts[4].strip().casefold()
        rating = rating_match.group(1)
        review_text = _normalize_review_text(parts[7].strip())
        yield (platform, username, rating, review_text)


def validate_no_duplicate_reviews(files: Optional[list[str]] = None) -> None:
    """Raise ValueError if any Markdown review file contains duplicate review content."""
    filenames = files or [
        "Yuanta_App_Reviews.md",
        "SinoPac_App_Reviews.md",
        "Cathay_App_Reviews.md",
    ]

    errors = []
    for filename in filenames:
        path = Path(config.BASE_DIR) / filename
        keys = list(_iter_review_keys(path))
        counts = Counter(keys)
        duplicates = [(key, count) for key, count in counts.items() if count > 1]
        if duplicates:
            sample = "; ".join(
                f"{key[0]} / {key[1]} / {key[2]}★ x{count}"
                for key, count in duplicates[:5]
            )
            errors.append(f"{filename}: {len(duplicates)} duplicate groups ({sample})")

    if errors:
        raise ValueError("Review duplicate validation failed: " + " | ".join(errors))


if __name__ == "__main__":
    validate_no_duplicate_reviews()
    print("Review duplicate validation passed.")
