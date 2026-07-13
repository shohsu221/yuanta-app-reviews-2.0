"""
batch_appstore_fetch.py
========================
一次性批量爬取三大券商 App Store 評論
日期區間：2026-01-01 至 2026-05-27

使用方式：
    python batch_appstore_fetch.py

輸出：
    - batch_appstore_2026H1.csv      （全部評論 CSV）
    - batch_appstore_summary.txt     （統計摘要）
"""

import csv
import logging
import sys
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

# ── 加入 agent 目錄至 path，讓 import models / appstore_scraper 正常運作 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import requests
from models import Review
import appstore_scraper as asc

# ── 設定 ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

TW_TZ = timezone(timedelta(hours=8))

# 日期篩選區間（台北時間）
DATE_START = datetime(2026, 1, 1, 0, 0, 0, tzinfo=TW_TZ)
DATE_END   = datetime(2026, 5, 27, 23, 59, 59, tzinfo=TW_TZ)

# 三家券商設定（App Store ID 已確認）
APPS = [
    {
        "name": "元大投資先生",
        "short_name": "Yuanta",
        "appstore_id": "1382114621",
    },
    {
        "name": "國泰證券",
        "short_name": "Cathay",
        "appstore_id": "1228503534",
    },
    {
        "name": "永豐大戶投",
        "short_name": "SinoPac",
        "appstore_id": "1551600164",
    },
]

OUTPUT_CSV = os.path.join(SCRIPT_DIR, "batch_appstore_2026H1.csv")
OUTPUT_SUMMARY = os.path.join(SCRIPT_DIR, "batch_appstore_summary.txt")

# 每個 App 最多抓取幾則（RSS 上限約 500 則，設大一點確保覆蓋）
FETCH_COUNT = 500


# ── 核心：帶日期過濾的爬取 ────────────────────────────────────

def fetch_filtered(app_id: str, app_name: str) -> list:
    """
    抓取 App Store 評論，只保留在 DATE_START ~ DATE_END 區間內的。
    若最老的一批評論都比 DATE_START 新，會繼續拉更多頁；
    若已超過 DATE_START 則停止（RSS 是依時間排序）。
    """
    logger.info(f"── 開始爬取【{app_name}】（ID: {app_id}）")

    all_reviews: list[Review] = []

    # ① 先用 HTML 水合（通常能抓到 8~16 則最新）
    html_reviews = asc._fetch_via_html_hydration(app_id, FETCH_COUNT, "tw")
    logger.info(f"   HTML 水合取得 {len(html_reviews)} 則")
    all_reviews.extend(html_reviews)

    # ② 用 RSS 翻頁（每頁 50 則，10 頁 = 500 則）
    rss_reviews = _fetch_rss_with_date_filter(app_id, app_name)
    logger.info(f"   RSS 取得 {len(rss_reviews)} 則")
    all_reviews.extend(rss_reviews)

    # ③ 若兩者都沒拿到，備援用 amp-api
    if not all_reviews:
        logger.warning(f"   RSS+HTML 皆無結果，改用 amp-api...")
        all_reviews = asc._fetch_via_amp_api(app_id, FETCH_COUNT, "tw")

    # 去重
    seen = set()
    unique = []
    for r in all_reviews:
        k = r.content_dedup_key()
        if k not in seen:
            seen.add(k)
            unique.append(r)

    # 日期篩選
    in_range = [
        r for r in unique
        if DATE_START <= r.date <= DATE_END
    ]

    # 依日期排序（新→舊）
    in_range.sort(key=lambda r: r.date, reverse=True)

    logger.info(f"   篩選後（{DATE_START.date()} ~ {DATE_END.date()}）：{len(in_range)} 則")
    return in_range


def _fetch_rss_with_date_filter(app_id: str, app_name: str) -> list:
    """
    翻頁式 RSS 爬取，一旦某頁最舊的評論早於 DATE_START，即停止翻頁。
    """
    results = []
    stop_early = False

    for page in range(1, 11):
        url = (
            f"https://itunes.apple.com/tw/rss/customerreviews/"
            f"page={page}/id={app_id}/sortBy=mostRecent/json"
        )
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                logger.debug(f"   RSS page {page} 狀態碼 {resp.status_code}，略過")
                time.sleep(0.5)
                continue

            data = resp.json()
            feed = data.get("feed", {})
            entries = feed.get("entry", [])
            if not entries:
                logger.debug(f"   RSS page {page} 無資料，停止翻頁")
                break

            if isinstance(entries, dict):
                entries = [entries]

            page_reviews = []
            for entry in entries:
                if "im:rating" not in entry:
                    continue
                r = asc._parse_rss_entry(entry)
                if r:
                    page_reviews.append(r)

            if not page_reviews:
                break

            results.extend(page_reviews)

            # 若此頁最舊的評論早於起始日，不需再往後翻頁
            oldest_in_page = min(r.date for r in page_reviews)
            if oldest_in_page < DATE_START:
                logger.debug(f"   RSS page {page} 最舊評論 {oldest_in_page.date()} < {DATE_START.date()}，停止翻頁")
                stop_early = True
                break

            time.sleep(0.3)  # 禮貌性延遲，避免被 rate-limit

        except Exception as e:
            logger.warning(f"   RSS page {page} 例外：{e}")
            time.sleep(1)
            continue

        if stop_early:
            break

    return results


# ── 輸出 ──────────────────────────────────────────────────────

def write_csv(all_data: dict[str, list]):
    """將所有 App 的評論寫入單一 CSV 檔。"""
    fieldnames = ["app_name", "date", "platform", "username", "rating", "version", "title", "content"]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for app_name, reviews in all_data.items():
            for r in reviews:
                writer.writerow({
                    "app_name": app_name,
                    "date": r.date.strftime("%Y-%m-%d %H:%M"),
                    "platform": r.platform,
                    "username": r.username,
                    "rating": r.rating,
                    "version": r.version,
                    "title": r.title or "",
                    "content": r.content,
                })

    logger.info(f"✅ CSV 已儲存：{OUTPUT_CSV}")


def write_summary(all_data: dict[str, list]):
    """產生文字統計摘要。"""
    lines = []
    lines.append("=" * 60)
    lines.append(f"  App Store 評論批量爬取摘要")
    lines.append(f"  日期區間：{DATE_START.date()} ～ {DATE_END.date()}")
    lines.append(f"  爬取時間：{datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M')}（台北時間）")
    lines.append("=" * 60)

    grand_total = 0
    for app_name, reviews in all_data.items():
        lines.append(f"\n【{app_name}】  共 {len(reviews)} 則")
        if reviews:
            avg = sum(r.rating for r in reviews) / len(reviews)
            dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for r in reviews:
                if r.rating in dist:
                    dist[r.rating] += 1
            lines.append(f"  平均評分：{avg:.2f} ★")
            for star, cnt in sorted(dist.items()):
                pct = cnt / len(reviews) * 100
                lines.append(f"  {star}★：{cnt} 則 ({pct:.1f}%)")
            oldest = min(r.date for r in reviews)
            newest = max(r.date for r in reviews)
            lines.append(f"  最早評論：{oldest.strftime('%Y-%m-%d')}")
            lines.append(f"  最新評論：{newest.strftime('%Y-%m-%d')}")
        grand_total += len(reviews)

    lines.append(f"\n{'=' * 60}")
    lines.append(f"  三家合計：{grand_total} 則 App Store 評論")
    lines.append("=" * 60)

    summary_text = "\n".join(lines)
    print(summary_text)

    with open(OUTPUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write(summary_text)

    logger.info(f"✅ 摘要已儲存：{OUTPUT_SUMMARY}")


# ── 主流程 ────────────────────────────────────────────────────

def main():
    logger.info(f"🚀 開始批量爬取 App Store 評論")
    logger.info(f"   日期區間：{DATE_START.date()} ～ {DATE_END.date()}")
    logger.info(f"   目標券商：{[a['name'] for a in APPS]}")
    logger.info("")

    all_data = {}

    for app in APPS:
        reviews = fetch_filtered(app["appstore_id"], app["name"])
        all_data[app["name"]] = reviews
        logger.info(f"   [{app['name']}] 完成，共 {len(reviews)} 則\n")
        time.sleep(1)  # 不同 App 之間的延遲

    write_csv(all_data)
    write_summary(all_data)

    logger.info("\n🎉 全部完成！")
    logger.info(f"   CSV  → {OUTPUT_CSV}")
    logger.info(f"   摘要 → {OUTPUT_SUMMARY}")


if __name__ == "__main__":
    main()
