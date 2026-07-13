"""
web_data.py — Single source of truth for every number rendered by
`Yuanta_Reviews_Web.html`.

Both web_sync.py (which injects the numbers into the dashboard) and
validate_dashboard.py (which verifies them) import from here, so the "written"
value and the "expected" value can never drift apart.

The dashboard is a 2026 Q1–Q2 review snapshot: Q1 = months 1–3, Q2 = months 4–6.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import config

# Deployed file that the crawler now maintains end-to-end.
WEB_HTML = "Yuanta_Reviews_Web.html"

# (brand label used inside Yuanta_Reviews_Web.html, Markdown source file, CSS token)
BRANDS = [
    ("元大投資先生", "Yuanta_App_Reviews.md", "yuanta"),
    ("永豐大戶投", "SinoPac_App_Reviews.md", "sinopac"),
    ("國泰證券", "Cathay_App_Reviews.md", "cathay"),
]
ORDER = [css for _, _, css in BRANDS]

_ROW_RE = re.compile(r"^\|\s*\d+\s*\|")


def _parse_reviews(brand: str, filename: str) -> list[dict]:
    """Parse one brand's detail table into review dicts.

    Column layout (see md_writer._format_row):
      | 序號 | 時間 | 平台 | 用戶 | 評分 | 版本 | 評論標題與內容 | 客服回覆 |
    md_writer already replaces newlines with spaces and "|" with "｜", so a naive
    split on "|" is safe.
    """
    rows: list[dict] = []
    path = Path(config.BASE_DIR) / filename
    for line in path.read_text(encoding="utf-8").splitlines():
        if not _ROW_RE.match(line):
            continue
        parts = line.split("|")
        if len(parts) < 9:
            continue
        try:
            dt = datetime.strptime(parts[2].strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        rating_match = re.search(r"\((\d)\)", parts[5])
        if not rating_match:
            continue
        rows.append({
            "brand": brand,
            "date": parts[2].strip(),
            "platform": parts[3].strip(),
            "version": parts[6].strip(),
            "user": parts[4].strip(),
            "rating": int(rating_match.group(1)),
            "text": parts[7].strip(),
            "_dt": dt,
        })
    return rows


def load_reviews() -> list[dict]:
    """All reviews across brands, newest-first (the order Web.html renders)."""
    reviews: list[dict] = []
    for brand, filename, _ in BRANDS:
        reviews.extend(_parse_reviews(brand, filename))
    reviews.sort(key=lambda r: r["_dt"], reverse=True)
    return reviews


def all_reviews_json(reviews: list[dict]) -> str:
    """Serialize to the exact object shape used by `const allReviews = [...]`."""
    payload = [
        {
            "brand": r["brand"],
            "date": r["date"],
            "platform": r["platform"],
            "version": r["version"],
            "user": r["user"],
            "rating": r["rating"],
            "text": r["text"],
        }
        for r in reviews
    ]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _avg(rows: list[dict]) -> float:
    return round(sum(r["rating"] for r in rows) / len(rows), 2) if rows else 0.0


def _quarter(rows: list[dict], quarter: int) -> list[dict]:
    lo, hi = (1, 3) if quarter == 1 else (4, 6)
    return [r for r in rows if lo <= r["_dt"].month <= hi]


def _dist_5_to_1(rows: list[dict]) -> list[int]:
    return [sum(1 for r in rows if r["rating"] == n) for n in range(5, 0, -1)]


def _pct(part: int, whole: int, decimals: int = 1) -> float:
    return round(part / whole * 100, decimals) if whole else 0.0


def _plat(rows: list[dict], platform: str) -> list[dict]:
    return [r for r in rows if r["platform"] == platform]


# Delta between two quarter averages, computed from the *displayed* (2-dp) values
# so the card's visible arithmetic (Q2 − Q1 = Δ) always checks out.
def _delta(q1_rows: list[dict], q2_rows: list[dict]) -> float:
    return round(_avg(q2_rows) - _avg(q1_rows), 2)


def compute_stats(reviews: list[dict] | None = None) -> dict:
    """Every number the dashboard shows, computed from the Markdown data."""
    reviews = reviews if reviews is not None else load_reviews()
    by_brand = {css: [r for r in reviews if r["brand"] == brand]
                for brand, _, css in BRANDS}
    q1 = {css: _quarter(by_brand[css], 1) for css in ORDER}
    q2 = {css: _quarter(by_brand[css], 2) for css in ORDER}
    q2_all = [r for css in ORDER for r in q2[css]]
    yuanta = ORDER[0]
    GP, AS = "Google Play", "App Store"

    y_q1, y_q2 = len(q1[yuanta]), len(q2[yuanta])
    dates = sorted(r["date"] for r in reviews)

    # ── all-brand Q2 monthly trend (Apr/May/Jun) ──
    q2_month = {m: [r for r in q2_all if r["_dt"].month == m] for m in (4, 5, 6)}
    n_q2 = len(q2_all)

    return {
        "total": len(reviews),
        "newest_date": dates[-1][:10] if dates else "",   # YYYY-MM-DD
        "oldest_date": dates[0][:10] if dates else "",
        "q2_avg": _avg(q2_all),
        "q2_low_pct": round(_pct(sum(1 for r in q2_all if r["rating"] <= 2),
                                 len(q2_all), 0)),
        # ── hero brand cards (Q2) ──
        "brand_q1_avg": [_avg(q1[css]) for css in ORDER],
        "brand_q2_avg": [_avg(q2[css]) for css in ORDER],
        "brand_q2_count": [len(q2[css]) for css in ORDER],
        "brand_q2_1star_pct": [_pct(sum(1 for r in q2[css] if r["rating"] == 1),
                                    len(q2[css])) for css in ORDER],
        "brand_delta": [_delta(q1[css], q2[css]) for css in ORDER],
        # ── whole-dataset per-brand (header, deep-dive, Tab-2) ──
        "brand_total": [len(by_brand[css]) for css in ORDER],
        "brand_overall_avg": [_avg(by_brand[css]) for css in ORDER],
        "brand_gp_count": [len(_plat(by_brand[css], GP)) for css in ORDER],
        "brand_as_count": [len(_plat(by_brand[css], AS)) for css in ORDER],
        "brand_low12_count": [sum(1 for r in by_brand[css] if r["rating"] <= 2)
                              for css in ORDER],
        # ── competitor snapshot: per-platform Q1/Q2 averages + deltas ──
        "brand_gp_q1_avg": [_avg(_plat(q1[css], GP)) for css in ORDER],
        "brand_gp_q2_avg": [_avg(_plat(q2[css], GP)) for css in ORDER],
        "brand_gp_delta": [_delta(_plat(q1[css], GP), _plat(q2[css], GP)) for css in ORDER],
        "brand_as_q1_avg": [_avg(_plat(q1[css], AS)) for css in ORDER],
        "brand_as_q2_avg": [_avg(_plat(q2[css], AS)) for css in ORDER],
        "brand_as_delta": [_delta(_plat(q1[css], AS), _plat(q2[css], AS)) for css in ORDER],
        # ── charts ──
        "yuanta_star_q1": _dist_5_to_1(q1[yuanta]),
        "yuanta_star_q2": _dist_5_to_1(q2[yuanta]),
        "yuanta_donut": [y_q1, y_q2],
        "yuanta_q1_share": _pct(y_q1, y_q1 + y_q2),
        "yuanta_q2_share": _pct(y_q2, y_q1 + y_q2),
        # ── Q2 monthly trend (all brands) + June low-score counts per brand ──
        "q2_month_count": [len(q2_month[m]) for m in (4, 5, 6)],
        "q2_month_avg": [_avg(q2_month[m]) for m in (4, 5, 6)],
        "q2_month_width": [round(len(q2_month[m]) / n_q2 * 100) if n_q2 else 0 for m in (4, 5, 6)],
        "june_low": [sum(1 for r in q2[css] if r["_dt"].month == 6 and r["rating"] <= 2)
                     for css in ORDER],
    }
