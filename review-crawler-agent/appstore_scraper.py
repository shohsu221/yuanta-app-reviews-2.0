"""
appstore_scraper.py — App Store 評論爬蟲 + App Store ID 自動偵測
"""
import logging
import json
import os
import requests
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Optional

from models import Review

logger = logging.getLogger(__name__)

TW_TZ = timezone(timedelta(hours=8))
ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"


# ── App Store ID 自動偵測 ─────────────────────────────────────

def find_appstore_id(search_term: str, country: str = "tw") -> Optional[str]:
    """
    使用 iTunes Search API 搜尋 App，回傳數字 App ID 字串。
    結果按評分人數降序取第一筆（最熱門的同名 App）。
    """
    try:
        resp = requests.get(
            ITUNES_SEARCH_URL,
            params={
                "term": search_term,
                "country": country,
                "entity": "software",
                "limit": 10,
                "lang": "zh_TW",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        # 取 userRatingCountForCurrentVersion 最多的那個
        best = max(results, key=lambda x: x.get("userRatingCount", 0))
        app_id = str(best.get("trackId", ""))
        app_name = best.get("trackName", "")
        logger.info(f"  [App Store 偵測] 找到：{app_name}（ID: {app_id}）")
        return app_id if app_id else None
    except Exception as e:
        logger.error(f"  [App Store 偵測] 搜尋失敗：{e}")
        return None


# ── 評論抓取 ──────────────────────────────────────────────────

def fetch_reviews(app_id: str, app_name: str, count: int = 100,
                  country: str = "tw") -> list:
    """
    從 App Store 抓取最新的 count 則評論。
    來源優先順序：amp-api（即時，最完整）→ HTML 水合（頁面展示）→ RSS（歷史深度）。
    """
    logger.info(f"  [App Store] 開始抓取 {app_name}（ID: {app_id}，最多 {count} 則）...")

    # 1. HTML 水合（同時爬主頁 + see-all=reviews，並嘗試從 JSON 中提取 Bearer token）
    html_reviews = _fetch_via_html_hydration(app_id, count, country)

    # 2. amp-api（若 token 可用則主動呼叫，取得最即時資料）
    amp_reviews = []
    if _TOKEN_CACHE.get("token"):
        amp_reviews = _fetch_via_amp_api(app_id, count, country)
        logger.info(f"  [App Store amp-api] 取得 {len(amp_reviews)} 則即時評論")

    # 3. RSS（補充歷史深度）
    rss_reviews = _fetch_via_rss(app_id, count, country)
    logger.info(f"  [App Store RSS] 取得 {len(rss_reviews)} 則 RSS 歷史評論")

    # 4. 合併並去重（amp-api 最新優先）。
    #    App Store 各來源可能回傳不同時區/版本欄位，用內容指紋避免同一評論重複。
    combined = amp_reviews + html_reviews + rss_reviews
    seen = set()
    unique_reviews = []
    for r in combined:
        k = r.content_dedup_key()
        if k not in seen:
            seen.add(k)
            unique_reviews.append(r)

    # 5. 若三者皆無結果，最後備援再試一次 amp-api（強制刷新 token）
    if not unique_reviews:
        logger.warning("  [App Store] 所有來源皆無結果，強制刷新 token 後重試 amp-api...")
        unique_reviews = _fetch_via_amp_api(app_id, count, country)

    unique_reviews.sort(key=lambda r: r.date, reverse=True)
    logger.info(f"  [App Store] 成功取得 {len(unique_reviews)} 則去重評論")
    return unique_reviews[:count]


def _reply_match_key(username: str, rating: int, title: str, content: str) -> str:
    """建立 App Store 回覆資料與既有 Review 之間的穩定比對 key。"""
    import re

    def norm(value: str) -> str:
        value = (value or "").replace("\n", " ").replace("|", "｜").strip()
        value = re.sub(r"\s+", " ", value)
        return value.casefold()

    return f"{norm(username)}|{int(rating or 0)}|{norm(title)}|{norm(content)}"


def _parse_apple_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TW_TZ)
    except Exception:
        return None


def _enrich_with_developer_replies(
    app_id: str,
    country: str,
    reviews: list[Review],
    count: int,
) -> None:
    """呼叫 appstore_replies.mjs，將 developerResponse 合併回 Review 物件。"""
    if not reviews:
        return

    # 多抓一點，因為 Apple reviews 端點排序不一定與 RSS 完全一致。
    reply_count = max(count, min(count * 3, 300))
    reply_rows = fetch_developer_replies(app_id, count=reply_count, country=country)
    apply_developer_replies(reviews, reply_rows)


def apply_developer_replies(reviews: list[Review], reply_rows: list[dict]) -> int:
    """將已抓到的 App Store developerResponse rows 合併回 Review 物件。"""
    if not reviews or not reply_rows:
        return 0

    reply_by_key = {}
    for row in reply_rows:
        body = (row.get("replyBody") or "").strip()
        if not body:
            continue
        key = _reply_match_key(
            row.get("userName", ""),
            row.get("rating", 0),
            row.get("title", ""),
            row.get("review", ""),
        )
        reply_by_key[key] = {
            "content": body,
            "date": _parse_apple_datetime(row.get("replyModified", "")),
        }

    matched = 0
    for review in reviews:
        key = _reply_match_key(
            review.username,
            review.rating,
            review.title or "",
            review.content,
        )
        reply = reply_by_key.get(key)
        if not reply:
            continue
        review.reply_content = reply["content"]
        review.reply_date = reply["date"]
        matched += 1

    if matched:
        logger.info(f"  [App Store replies] 已補齊 {matched} 則客服回覆")
    return matched


def fetch_developer_replies(app_id: str, count: int = 300, country: str = "tw") -> list[dict]:
    """抓取 App Store developerResponse 原始列，供 MD 既有資料回填使用。"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "appstore_replies.mjs")
    if not os.path.exists(script):
        return []

    try:
        proc = subprocess.run(
            ["node", script, app_id, country, str(count)],
            check=False,
            text=True,
            capture_output=True,
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning(f"  [App Store replies] 客服回覆抓取略過：{e}")
        return []

    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip().splitlines()
        detail = msg[-1] if msg else f"exit {proc.returncode}"
        logger.warning(f"  [App Store replies] 客服回覆抓取失敗：{detail}")
        return []

    try:
        rows = json.loads(proc.stdout or "[]")
    except Exception as e:
        logger.warning(f"  [App Store replies] JSON 解析失敗：{e}")
        return []

    return rows if isinstance(rows, list) else []


def _fetch_via_html_hydration(app_id: str, count: int, country: str) -> list:
    """
    透過 App Store 網頁 HTML 中的 serialized-server-data 抓取最新評論。
    同時爬取主頁與 see-all=reviews 頁，突破單頁 8 則的限制。
    """
    import re
    import json

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-TW,zh;q=0.9",
    }

    # 同時爬主頁和「全部評論」頁，後者通常包含更多筆
    urls_to_try = [
        f"https://apps.apple.com/{country}/app/id{app_id}",
        f"https://apps.apple.com/{country}/app/id{app_id}?see-all=reviews",
    ]

    reviews_dict = {}  # 以 id 去重
    JWT_PAT = re.compile(r'(eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})')

    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"  [App Store HTML] 網頁請求失敗: {url} Status {resp.status_code}")
                continue

            resp.encoding = 'utf-8'
            html = resp.text

            match = re.search(r'<script[^>]*serialized-server-data[^>]*>(.*?)</script>', html, re.DOTALL)
            if not match:
                logger.warning(f"  [App Store HTML] 找不到 serialized-server-data: {url}")
                continue

            raw_json = match.group(1).strip()

            # 順便從 JSON 原文中提取 Bearer token（若尚未快取）
            if not _TOKEN_CACHE.get("token"):
                tm = JWT_PAT.search(raw_json)
                if tm:
                    _TOKEN_CACHE["token"] = tm.group(1)
                    logger.info("  [Token] Bearer token 從 serialized-server-data 取得")

            root = json.loads(raw_json)
            data_list = root.get("data", [])
            if not data_list:
                continue

            sub_data = data_list[0].get("data", {})
            shelf_mapping = sub_data.get("shelfMapping", {})

            for shelf_key in ["allProductReviews", "userProductReviews", "editorialProductReviews"]:
                shelf = shelf_mapping.get(shelf_key, {})
                items = shelf.get("items", [])
                for item in items:
                    r = item.get("review", {})
                    if r and "id" in r:
                        reviews_dict[r["id"]] = r

        except Exception as e:
            logger.error(f"  [App Store HTML] 網頁爬取與解析例外 {url}：{e}")

    results = []
    for r_id, r in reviews_dict.items():
        try:
            date_str = r.get("date", "")
            if date_str:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dt_tw = dt.astimezone(TW_TZ)
            else:
                dt_tw = datetime.now(TW_TZ)

            title = r.get("title", "")
            content = r.get("contents", "")
            rating = int(r.get("rating", 0))
            author = r.get("reviewerName", "匿名用戶").strip() or "匿名用戶"

            results.append(Review(
                platform="App Store",
                date=dt_tw,
                username=author,
                rating=rating,
                version="未知",
                title=title if title else None,
                content=content,
                raw_id=r_id,
            ))
        except Exception as ex:
            logger.debug(f"  [App Store HTML] 解析單筆評論失敗: {ex}")
            continue

    results.sort(key=lambda r: r.date, reverse=True)
    logger.info(f"  [App Store HTML] 取得 {len(results)} 則即時網頁評論")
    return results[:count]



def _fetch_via_rss(app_id: str, count: int, country: str) -> list:
    """
    透過 iTunes RSS API (JSON 格式) 抓取評論。
    同時嘗試帶 page= 與不帶 page= 兩種 URL 格式，應對 Apple 不同時期的 API 行為。
    """
    results = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    # Apple RSS 有兩種路徑格式，新版有時不支援 page= 參數
    url_templates = [
        f"https://itunes.apple.com/{country}/rss/customerreviews/page={{page}}/id={app_id}/sortBy=mostRecent/json",
        f"https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortBy=mostRecent/json",
    ]

    for page in range(1, 11):
        got_any = False
        for url_tmpl in url_templates:
            url = url_tmpl.format(page=page)
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code != 200:
                    continue

                try:
                    data = resp.json()
                except Exception:
                    continue

                feed = data.get("feed", {})
                entries = feed.get("entry", [])
                if not entries:
                    continue

                if isinstance(entries, dict):
                    entries = [entries]

                for entry in entries:
                    if "im:rating" not in entry:
                        continue
                    review_obj = _parse_rss_entry(entry)
                    if review_obj:
                        results.append(review_obj)

                got_any = True
                break  # 本頁成功，跳過另一種 URL 格式

            except Exception as e:
                logger.warning(f"  [App Store RSS] Page {page} 爬取例外：{e}")
                continue

        # 不帶 page= 的格式只有一頁，取到後結束
        if not got_any and page > 1:
            break
        if len(results) >= count:
            break

    seen = set()
    unique_results = []
    for r in results:
        k = r.content_dedup_key()
        if k not in seen:
            seen.add(k)
            unique_results.append(r)

    unique_results.sort(key=lambda r: r.date, reverse=True)
    return unique_results[:count]


def _parse_rss_entry(entry: dict) -> Optional[Review]:
    """將 RSS entry 解析成統一的 Review 格式。"""
    try:
        raw_id = entry.get("id", {}).get("label", "")
        author = entry.get("author", {}).get("name", {}).get("label", "匿名用戶").strip()
        version = entry.get("im:version", {}).get("label", "未知").strip()
        rating = int(entry.get("im:rating", {}).get("label", "0"))
        title = entry.get("title", {}).get("label", "").strip()
        content = entry.get("content", {}).get("label", "").strip()

        updated_str = entry.get("updated", {}).get("label", "")
        if updated_str:
            try:
                # 格式例如： "2026-01-24T17:05:38-07:00"
                dt = datetime.fromisoformat(updated_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dt_tw = dt.astimezone(TW_TZ)
            except Exception:
                dt_tw = datetime.now(TW_TZ)
        else:
            dt_tw = datetime.now(TW_TZ)

        return Review(
            platform="App Store",
            date=dt_tw,
            username=author or "匿名用戶",
            rating=rating,
            version=version or "未知",
            title=title if title else None,
            content=content,
            raw_id=raw_id,
        )
    except Exception as e:
        logger.debug(f"  [App Store RSS] 解析單筆評論失敗: {e}")
        return None


# ── Token 快取 ────────────────────────────────────────────────
_TOKEN_CACHE = {"token": None}


def _get_appstore_token(force_refresh: bool = False) -> Optional[str]:
    """
    從 Apple App Store 動態取得 Bearer Token。
    依序嘗試：頁面 HTML 直接提取 → JS bundle 掃描（多種 URL 模式）。
    """
    import re as _re

    if not force_refresh and _TOKEN_CACHE["token"]:
        return _TOKEN_CACHE["token"]

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-TW,zh;q=0.9",
    }

    JWT_PAT = r'(eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})'

    # 多頁備援，任一頁能取到 token 即止
    test_pages = [
        "https://apps.apple.com/tw/app/id1382114621",
        "https://apps.apple.com/tw/app/id1551600164",
        "https://apps.apple.com/tw/app/id1228503534",
        "https://apps.apple.com/tw/charts/iphone",
    ]

    for page_url in test_pages:
        try:
            page_resp = requests.get(page_url, headers=HEADERS, timeout=15)
            if page_resp.status_code != 200:
                continue
            html = page_resp.text

            # 策略 1：JWT 直接嵌在頁面 HTML 中（meta tag 或 inline script）
            m = _re.search(JWT_PAT, html)
            if m:
                token = m.group(1)
                _TOKEN_CACHE["token"] = token
                logger.info("  [Token] Bearer token 從頁面 HTML 取得")
                return token

            # 策略 2：從 script src 找 JS bundle，支援絕對與相對路徑
            script_urls = []
            for pat in [
                r'src="(https://[^"]+\.js[^"]*)"',
                r'src="(/[^"?#]+\.js)"',
                r'"(https://[^"]+/assets/[^"]+\.js)"',
            ]:
                script_urls.extend(_re.findall(pat, html))

            # 相對路徑補全
            abs_urls = []
            for u in script_urls:
                if u.startswith("http"):
                    abs_urls.append(u)
                elif u.startswith("/"):
                    abs_urls.append("https://apps.apple.com" + u)

            for script_url in abs_urls[:15]:
                try:
                    js_resp = requests.get(script_url, headers=HEADERS, timeout=10)
                    m = _re.search(JWT_PAT, js_resp.text)
                    if m:
                        token = m.group(1)
                        _TOKEN_CACHE["token"] = token
                        logger.info("  [Token] Bearer token 從 JS bundle 取得")
                        return token
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"  [Token] {page_url} 載入失敗：{e}")
            continue

    logger.warning("  [Token] 無法取得 Bearer token")
    return None


def _fetch_via_amp_api(app_id: str, count: int, country: str) -> list:
    """
    透過 Apple amp-api.apps.apple.com 抓取評論。
    先取得 Bearer Token，再呼叫官方 API。
    """
    import urllib.parse as _urlparse

    token = _get_appstore_token()
    if not token:
        logger.warning("  [amp-api] 無 Bearer Token，App Store 評論跳過")
        return []

    results = []
    offset = 0
    limit = min(20, count)

    while len(results) < count:
        url = f"https://amp-api.apps.apple.com/v1/catalog/{country}/apps/{app_id}/reviews"
        params = {
            "l": "zh-TW",
            "offset": str(offset),
            "limit": str(limit),
            "platform": "web",
            "additionalPlatforms": "appletv,ipad,iphone,mac",
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Origin": "https://apps.apple.com",
            "Referer": f"https://apps.apple.com/{country}/app/id{app_id}",
            "Accept": "application/json",
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 401:
                logger.warning("  [amp-api] Token 過期，重新取得...")
                token = _get_appstore_token(force_refresh=True)
                if not token:
                    break
                continue
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"  [amp-api] 請求失敗 (offset={offset})：{e}")
            break

        entries = data.get("data", [])
        if not entries:
            break

        for entry in entries:
            try:
                attr = entry.get("attributes", {})
                date_str = attr.get("date", "")
                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    dt_tw = dt.astimezone(TW_TZ)
                except Exception:
                    dt_tw = datetime.now(TW_TZ)

                results.append(Review(
                    platform="App Store",
                    date=dt_tw,
                    username=attr.get("userName", "匿名用戶").strip() or "匿名用戶",
                    rating=int(attr.get("rating", 0)),
                    version=attr.get("version", "未知") or "未知",
                    title=attr.get("title", "").strip() or None,
                    content=attr.get("review", "").strip(),
                    raw_id=entry.get("id", ""),
                ))
            except Exception:
                continue

        next_url = data.get("next", None)
        if not next_url or len(results) >= count:
            break
        qs = _urlparse.parse_qs(_urlparse.urlparse(next_url).query)
        offset = int(qs.get("offset", [offset + limit])[0])

    return results[:count]
