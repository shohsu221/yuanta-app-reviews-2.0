#!/usr/bin/env python3
"""
crawler_runner.py — 三大券商 App 評論爬蟲引擎庫

提供 process_app / update_database / resolve_appstore_id 等核心爬蟲函數，
供 main.py（專案主入口）呼叫。本模組不提供命令列入口。
"""

import logging
import os
import sys
from datetime import datetime, timezone, timedelta

# ── 確保 crawler/ 目錄在 Python path 中 ──────────────────────────
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

import json
import re
from pathlib import Path
import config
import gplay_scraper
import appstore_scraper
import notifier
from models import Review

logger = logging.getLogger(__name__)

TW_TZ = timezone(timedelta(hours=8))


# ══════════════════════════════════════════════════════════════
# JSON 資料庫輔助與去重寫入邏輯
# ══════════════════════════════════════════════════════════════

def review_to_dict(r: Review) -> dict:
    return {
        "platform": r.platform,
        "date": r.date.isoformat(),
        "username": r.username,
        "rating": r.rating,
        "version": r.version,
        "title": r.title,
        "content": r.content,
        "raw_id": r.raw_id,
        "reply_content": r.reply_content,
        "reply_date": r.reply_date.isoformat() if r.reply_date else None,
    }


def dict_to_review(d: dict) -> Review:
    reply_date = None
    if d.get("reply_date"):
        reply_date = datetime.fromisoformat(d["reply_date"])
    return Review(
        platform=d["platform"],
        date=datetime.fromisoformat(d["date"]),
        username=d["username"],
        rating=int(d["rating"]),
        version=d["version"],
        title=d.get("title"),
        content=d["content"],
        raw_id=d.get("raw_id", ""),
        reply_content=d.get("reply_content"),
        reply_date=reply_date
    )


def get_quarter_filename(short_name: str, dt: datetime) -> str:
    brand_lower = short_name.lower()
    quarter = (dt.month - 1) // 3 + 1
    return f"{brand_lower}_{dt.year}_q{quarter}.json"


def get_existing_reviews(short_name: str) -> list[Review]:
    """載入該 App 所有季度 JSON 檔案中的評論。"""
    reviews = []
    comments_dir = Path(config.COMMENTS_DIR)
    if not comments_dir.exists():
        return []

    brand_prefix = f"{short_name.lower()}_"
    for file in comments_dir.glob(f"{brand_prefix}*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                reviews.extend([dict_to_review(item) for item in data])
        except Exception as e:
            logger.error(f"載入歷史資料失敗 {file.name}: {e}")
    return reviews


def update_database(
    short_name: str,
    new_reviews: list[Review],
) -> tuple[int, int, int]:
    """
    將新評論去重後，增量寫入對應的季度 JSON 檔案中。
    """
    existing_reviews = get_existing_reviews(short_name)
    existing_keys = {r.dedup_key() for r in existing_reviews}
    existing_content_keys = {r.content_dedup_key() for r in existing_reviews}

    start_date = None
    if config.REVIEW_START_DATE:
        start_date = datetime.strptime(config.REVIEW_START_DATE, "%Y-%m-%d").replace(tzinfo=TW_TZ)
    end_date = None
    if config.REVIEW_END_DATE:
        end_date = datetime.strptime(config.REVIEW_END_DATE, "%Y-%m-%d").replace(tzinfo=TW_TZ)
        end_date = end_date.replace(hour=23, minute=59, second=59)

    new_gplay = 0
    new_appstore = 0
    updates_by_file = {}

    existing_by_file = {}
    for r in existing_reviews:
        fn = get_quarter_filename(short_name, r.date)
        if fn not in existing_by_file:
            existing_by_file[fn] = []
        existing_by_file[fn].append(r)

    for r in new_reviews:
        if start_date and r.date < start_date:
            continue
        if end_date and r.date > end_date:
            continue

        legacy_key = r.dedup_key()
        content_key = r.content_dedup_key()

        if legacy_key in existing_keys or content_key in existing_content_keys:
            if r.reply_content:
                for ex_r in existing_reviews:
                    if ex_r.dedup_key() == legacy_key or ex_r.content_dedup_key() == content_key:
                        if not ex_r.reply_content:
                            ex_r.reply_content = r.reply_content
                            ex_r.reply_date = r.reply_date
                            fn = get_quarter_filename(short_name, ex_r.date)
                            if fn not in updates_by_file:
                                updates_by_file[fn] = list(existing_by_file.get(fn, []))
                            break
            continue

        existing_keys.add(legacy_key)
        existing_content_keys.add(content_key)

        if r.platform == "Google Play":
            new_gplay += 1
        elif r.platform == "App Store":
            new_appstore += 1

        fn = get_quarter_filename(short_name, r.date)
        if fn not in updates_by_file:
            updates_by_file[fn] = list(existing_by_file.get(fn, []))
        updates_by_file[fn].append(r)

    comments_dir = Path(config.COMMENTS_DIR)
    comments_dir.mkdir(parents=True, exist_ok=True)

    for fn, reviews_list in updates_by_file.items():
        reviews_list.sort(key=lambda x: x.date, reverse=True)
        file_path = comments_dir / fn
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump([review_to_dict(r) for r in reviews_list], f, ensure_ascii=False, indent=2)

    total_count = len(existing_reviews) + new_gplay + new_appstore
    return new_gplay, new_appstore, total_count


def backfill_appstore_replies(short_name: str, reply_rows: list[dict]) -> int:
    """用 App Store developerResponse 回填既有 JSON 評論的客服回覆。"""
    if not reply_rows:
        return 0

    reply_by_key = {}
    for row in reply_rows:
        content = (row.get("replyBody") or "").strip()
        if not content:
            continue
        reply_date = None
        if row.get("replyModified"):
            try:
                dt = datetime.fromisoformat(row["replyModified"].replace("Z", "+00:00"))
                reply_date = dt.astimezone(TW_TZ)
            except Exception:
                pass

        title = row.get("title") or ""
        review_text = row.get("review") or ""
        combined_text = f"【{title}】 {review_text}" if title else review_text
        combined_text = combined_text.replace("\n", " ").replace("|", "｜").strip()
        combined_text = re.sub(r"\s+", " ", combined_text).casefold()

        user_key = (row.get("userName") or "").strip().casefold()
        key = f"{user_key}|{int(row.get('rating', 0))}|{combined_text}"
        reply_by_key[key] = (content, reply_date)

    if not reply_by_key:
        return 0

    comments_dir = Path(config.COMMENTS_DIR)
    if not comments_dir.exists():
        return 0

    changed = 0
    brand_prefix = f"{short_name.lower()}_"

    for file in comments_dir.glob(f"{brand_prefix}*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            reviews = [dict_to_review(item) for item in data]

            file_changed = False
            for r in reviews:
                if r.platform != "App Store" or r.reply_content:
                    continue

                norm_text = r.normalized_review_text()
                user_key = r.username.strip().casefold()
                key = f"{user_key}|{r.rating}|{norm_text}"

                if key in reply_by_key:
                    content, reply_date = reply_by_key[key]
                    r.reply_content = content
                    r.reply_date = reply_date
                    file_changed = True
                    changed += 1

            if file_changed:
                with open(file, "w", encoding="utf-8") as f:
                    json.dump([review_to_dict(r) for r in reviews], f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"回填 {file.name} 客服回覆失敗: {e}")

    if changed:
        logger.info(f"已直接回填 App Store 客服回覆 {changed} 則")
    return changed


# ══════════════════════════════════════════════════════════════
# 核心執行邏輯
# ══════════════════════════════════════════════════════════════

def resolve_appstore_id(app: dict):  # -> Optional[str]
    """
    取得 App Store ID。
    若設定為 'AUTO'，嘗試用 iTunes Search API 搜尋並快取結果。
    """
    app_id = app.get("appstore_id", "AUTO")

    if app_id and app_id != "AUTO":
        return app_id

    logger.info(f"[{app['name']}] App Store ID 未設定，嘗試自動搜尋...")
    search_term = app.get("appstore_search_term", app["name"])
    found_id = appstore_scraper.find_appstore_id(search_term, country=config.COUNTRY)

    if found_id:
        config.save_appstore_id(app["short_name"], found_id)
        logger.info(f"[{app['name']}] App Store ID 已快取：{found_id}")
        return found_id
    else:
        logger.error(f"[{app['name']}] 無法自動取得 App Store ID，跳過 App Store 爬取")
        return None


def process_app(app: dict, fetch_count: int) -> tuple[int, int, int]:
    """
    處理單一 App：
    1. 分別爬取 Google Play 與 App Store
    2. 合併、去重、寫入 JSON 資料庫
    3. 發送通知
    """
    app_name = app["name"]
    short_name = app["short_name"]

    logger.info(f"\n{'='*60}")
    logger.info(f"▶  開始處理：{app_name}")
    logger.info(f"   資料庫目錄：{config.COMMENTS_DIR}")

    # Step 1: 爬取 Google Play
    gplay_reviews = gplay_scraper.fetch_reviews(
        app["gplay_id"], count=fetch_count
    )

    # Step 2: 爬取 App Store
    appstore_id = resolve_appstore_id(app)
    if appstore_id:
        appstore_reviews = appstore_scraper.fetch_reviews(
            app_id=appstore_id,
            app_name=app.get("appstore_search_term", app_name),
            count=fetch_count,
            country=config.COUNTRY,
        )
        appstore_reply_rows = appstore_scraper.fetch_developer_replies(
            appstore_id,
            count=max(fetch_count * 5, 500),
            country=config.COUNTRY,
        )
        appstore_scraper.apply_developer_replies(appstore_reviews, appstore_reply_rows)
    else:
        appstore_reviews = []
        appstore_reply_rows = []

    # Step 3: 合併所有新評論
    all_new_reviews = gplay_reviews + appstore_reviews

    if not all_new_reviews:
        logger.warning(f"[{app_name}] 兩平台均無法取得評論")
        notifier.notify_error(app_name, "兩平台均無法取得評論")
        existing_count = len(get_existing_reviews(short_name))
        return 0, 0, existing_count

    # Step 4: 寫入 JSON 資料庫（去重 + 增量追加）
    new_gplay, new_appstore, total = update_database(
        short_name=short_name,
        new_reviews=all_new_reviews,
    )

    if appstore_reply_rows:
        backfill_appstore_replies(short_name, appstore_reply_rows)

    # Step 5: 通知
    if new_gplay + new_appstore > 0:
        notifier.notify_success(app_name, new_gplay, new_appstore, total)
    else:
        notifier.notify_no_update(app_name)

    return new_gplay, new_appstore, total



if __name__ == "__main__":
    print("\n 提示：crawler_runner.py 已重構為純爬蟲引擎庫，不提供直接執行的命令列入口。")
    print("請至專案根目錄執行 main.py，例如：")
    print("  python main.py --run-now --count 5\n")
    sys.exit(1)
