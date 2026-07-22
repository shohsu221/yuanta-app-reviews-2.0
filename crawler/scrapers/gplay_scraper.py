"""
gplay_scraper.py — Google Play 評論爬蟲
"""
import sys
import time
import logging
from datetime import datetime, timezone, timedelta

from crawler.utils.models import Review

logger = logging.getLogger(__name__)

TW_TZ = timezone(timedelta(hours=8))


def fetch_reviews(gplay_id: str, count: int = 100) -> list[Review]:
    """
    從 Google Play 抓取最新的 count 則評論（台灣地區）。
    回傳按時間降序排列的 Review 列表。
    """
    try:
        from google_play_scraper import reviews as gplay_reviews, Sort
    except ImportError:
        logger.error("❌ 請先安裝套件：pip install google-play-scraper")
        return []

    logger.info(f"  [Google Play] 開始抓取 {gplay_id}（最多 {count} 則）...")

    try:
        result, _ = gplay_reviews(
            gplay_id,
            lang="zh_TW",
            country="tw",
            sort=Sort.NEWEST,
            count=count,
        )
    except Exception as e:
        logger.error(f"  [Google Play] 抓取失敗：{e}")
        return []

    reviews_list = []
    for r in result:
        try:
            dt_raw = r.get("at")
            if isinstance(dt_raw, datetime):
                # 確保有時區資訊
                if dt_raw.tzinfo is None:
                    dt_raw = dt_raw.replace(tzinfo=timezone.utc)
                dt_tw = dt_raw.astimezone(TW_TZ)
            else:
                dt_tw = datetime.now(TW_TZ)

            # 開發者/客服回覆（若有）
            reply_content = (r.get("replyContent") or "").strip() or None
            replied_raw = r.get("repliedAt")
            reply_date = None
            if reply_content and isinstance(replied_raw, datetime):
                if replied_raw.tzinfo is None:
                    replied_raw = replied_raw.replace(tzinfo=timezone.utc)
                reply_date = replied_raw.astimezone(TW_TZ)

            review = Review(
                platform="Google Play",
                date=dt_tw,
                username=r.get("userName", "匿名用戶").strip() or "匿名用戶",
                rating=int(r.get("score", 0)),
                version=r.get("appVersion", "未知") or "未知",
                title=None,
                content=(r.get("content") or "").strip(),
                raw_id=r.get("reviewId", ""),
                reply_content=reply_content,
                reply_date=reply_date,
            )
            reviews_list.append(review)
        except Exception as e:
            logger.warning(f"  [Google Play] 解析單筆評論失敗：{e}")
            continue

    logger.info(f"  [Google Play] 成功取得 {len(reviews_list)} 則評論")
    return reviews_list
