"""
md_writer.py — MD 檔案讀取、去重比對、增量寫入
"""
import re
import logging
from pathlib import Path
from datetime import datetime, time, timezone, timedelta
from collections import defaultdict

from typing import Optional
import config
from models import Review

logger = logging.getLogger(__name__)

TW_TZ = timezone(timedelta(hours=8))

# ── 解析現有 MD 去重 Key ────────────────────────────────────────

# 匹配評論表格每一列（寬鬆匹配，允許欄位中有 Markdown 符號）
_ROW_RE = re.compile(
    r"^\|\s*\d+\s*\|"           # | 序號 |
    r"\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\|"  # | 時間(YYYY-MM-DD HH:MM) |
    r"\s*([^|]+?)\s*\|"         # | 平台 |
    r"\s*([^|]+?)\s*\|",        # | 用戶名 |
    re.MULTILINE,
)


def _normalize_review_text(text: str) -> str:
    """正規化 MD/爬蟲評論文字，供內容指紋去重使用。"""
    text = _strip_red_tags(text)
    text = re.sub(r"\*\*【(.+?)】\*\*", r"【\1】", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\n", " ").replace("|", "｜").strip()
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


def _parse_row_fields(clean_row: str) -> Optional[dict]:
    """解析既有 MD 表格列，回傳去重與統計所需欄位。"""
    parts = clean_row.split("|")
    if len(parts) < 8:
        return None

    try:
        dt = datetime.strptime(parts[2].strip(), "%Y-%m-%d %H:%M").replace(tzinfo=TW_TZ)
    except Exception:
        return None

    rating_match = re.search(r"\((\d)\)", parts[5])
    if not rating_match:
        return None

    return {
        "date": dt,
        "platform": parts[3].strip(),
        "username": parts[4].strip(),
        "rating": int(rating_match.group(1)),
        "version": parts[6].strip(),
        "review_text": parts[7].strip(),
        "reply_text": parts[8].strip() if len(parts) > 9 else "",
    }


def _row_content_key(clean_row: str) -> Optional[str]:
    """從既有 MD 列建立跨來源內容指紋。"""
    fields = _parse_row_fields(clean_row)
    if not fields:
        return None

    user_key = fields["username"].strip().casefold()
    review_text = _normalize_review_text(fields["review_text"])
    return f"{fields['platform']}|content|{user_key}|{fields['rating']}|{review_text}"


def _appstore_reply_key(username: str, rating: int, review_text: str) -> str:
    """建立 App Store developerResponse 與 MD 表格列的比對 key。"""
    text = re.sub(r"^\*\*【(.+?)】\*\*\s*", r"【\1】 ", review_text or "")
    return (
        f"{(username or '').strip().casefold()}|"
        f"{int(rating or 0)}|"
        f"{_normalize_review_text(text)}"
    )


def _appstore_reply_row_key(row: dict) -> str:
    title = row.get("title") or ""
    review = row.get("review") or ""
    text = f"【{title}】 {review}" if title else review
    return _appstore_reply_key(row.get("userName", ""), row.get("rating", 0), text)


def _format_reply_text(content: str, modified: str = "") -> str:
    """格式化外部抓到的客服回覆為 MD 欄位文字。"""
    text = (content or "").replace("\n", " ").replace("|", "｜").strip()
    if not text:
        return ""

    if modified:
        try:
            dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            text = f"**[{dt.astimezone(TW_TZ).strftime('%Y-%m-%d')}]** {text}"
        except Exception:
            pass
    return text[:600]


def _strip_red_tags(row: str) -> str:
    """清除行中的紅色 HTML 標籤。"""
    row = re.sub(r"<font color=\"?red\"?>", "", row, flags=re.IGNORECASE)
    row = re.sub(r"</font>", "", row, flags=re.IGNORECASE)
    row = re.sub(r"<span style=\"color:\s*red;?\"?>", "", row, flags=re.IGNORECASE)
    row = re.sub(r"</span>", "", row, flags=re.IGNORECASE)
    return row


def get_existing_keys(md_path: str) -> set[str]:
    """
    讀取現有 MD 檔案，回傳所有評論的去重 Key 集合。
    格式與 Review.dedup_key() 一致：{platform}|{YYYYMMDDHHmm}|{username[:20]}
    """
    path = Path(md_path)
    if not path.exists():
        logger.info(f"  📄 {path.name} 尚不存在，將建立新檔案")
        return set()

    content = path.read_text(encoding="utf-8")
    content_clean = _strip_red_tags(content)
    keys = set()

    for m in _ROW_RE.finditer(content_clean):
        date_str = m.group(1).replace("-", "").replace(" ", "").replace(":", "")
        # date_str 現在是 "YYYYMMDDHHmm" 形式
        platform = m.group(2).strip()
        username = m.group(3).strip()[:20]
        keys.add(f"{platform}|{date_str}|{username}")

    logger.info(f"  📖 {path.name} 現有 {len(keys)} 筆評論記錄")
    return keys


# ── 統計計算 ──────────────────────────────────────────────────

def _calc_stats(reviews: list[Review]) -> dict:
    """計算各平台評論統計。"""
    platforms = {"Google Play": [], "App Store": []}
    for r in reviews:
        if r.platform in platforms:
            platforms[r.platform].append(r.rating)

    stats = {}
    for platform, ratings in platforms.items():
        if ratings:
            avg = sum(ratings) / len(ratings)
            dist = {i: ratings.count(i) for i in range(1, 6)}
        else:
            avg = 0.0
            dist = {i: 0 for i in range(1, 6)}

        stats[platform] = {
            "count": len(ratings),
            "avg": avg,
            "dist": dist,
        }

    # 雙平台合計
    all_ratings = [r.rating for r in reviews]
    if all_ratings:
        combined_avg = sum(all_ratings) / len(all_ratings)
        combined_dist = {i: all_ratings.count(i) for i in range(1, 6)}
    else:
        combined_avg = 0.0
        combined_dist = {i: 0 for i in range(1, 6)}

    stats["Combined"] = {
        "count": len(all_ratings),
        "avg": combined_avg,
        "dist": combined_dist,
    }
    return stats


def _stats_row(platform_label: str, s: dict) -> str:
    total = s["count"]
    avg = s["avg"]
    dist = s["dist"]

    def pct(n):
        return f"{n} ({n/total*100:.1f}%)" if total else f"{n} (0.0%)"

    return (
        f"| **{platform_label}** | {total} | {avg:.2f} ★ |"
        f" {pct(dist[1])} | {pct(dist[2])} | {pct(dist[3])} |"
        f" {pct(dist[4])} | {pct(dist[5])} |"
    )


# ── MD 格式化 ─────────────────────────────────────────────────

def _format_row(idx: int, review: Review, is_red: bool = False) -> str:
    """格式化單筆評論為 MD 表格列。"""
    date_str = review.date.strftime("%Y-%m-%d %H:%M")
    stars = "★" * review.rating + "☆" * (5 - review.rating)
    content = review.format_content_for_md()
    reply = review.format_reply_for_md()
    
    return (
        f"| {idx} | {date_str} | {review.platform} | {review.username} |"
        f" `{stars}` ({review.rating}) | {review.version} | {content} | {reply} |"
    )


def _format_existing_row(idx: int, item: dict) -> str:
    """重編既有列序號，並確保有「客服回覆」欄位。"""
    row = re.sub(r"^\|\s*\d+\s*\|", f"| {idx} |", item["clean_row_str"], count=1)
    reply = item.get("reply_text", "")
    parts = row.split("|")
    if len(parts) > 9:
        parts[8] = f" {reply} "
        return "|".join(parts)
    if len(parts) == 9:
        parts.insert(8, f" {reply} ")
        return "|".join(parts)
    return row


def _replace_row_reply(row: str, reply: str) -> str:
    """替換/補上既有 MD row 的客服回覆欄位。"""
    parts = row.split("|")
    if len(parts) > 9:
        parts[8] = f" {reply} "
        return "|".join(parts)
    if len(parts) == 9:
        parts.insert(8, f" {reply} ")
        return "|".join(parts)
    return row


_MD_HEADER = """\
# {app_name} 用戶評論數據報告（自動更新）

> **最後更新時間**：{last_updated}（台北時間）
> **本次新增評論**：{new_count} 則（Google Play {new_gplay} 則 ｜ App Store {new_appstore} 則）
> **資料累計總量**：雙平台共 {total_count} 則
> **目標應用程式**：{app_name}

---

## 一、 數據總覽

| 平台 | 評論總數 | 平均評分 | 1★ (%) | 2★ (%) | 3★ (%) | 4★ (%) | 5★ (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
{stats_rows}

---

## 二、 詳細評論列表

| 序號 | 時間 | 平台 | 用戶 | 評分 | 版本 | 評論標題與內容 | 客服回覆 |
| :---: | :--- | :--- | :--- | :---: | :--- | :--- | :--- |
"""


def _parse_existing_reviews_from_md(content: str) -> list[str]:
    """
    從現有 MD 中提取評論表格列（字串形式），
    用於在新評論前面接續。
    """
    # 找到詳細評論列表區段 (相容 '詳細評論列表' 或 '雙平台用戶評論列表')
    section_match = re.search(r"## 二、\s*[^|]*?評論列表.*?\n", content, re.DOTALL)
    if not section_match:
        return []

    # 找表格分隔線後的所有資料列
    after_header = content[section_match.end():]
    rows = []
    for line in after_header.splitlines():
        stripped = line.strip()
        # 跳過表頭、分隔列、空行
        if not stripped.startswith("|"):
            if rows:  # 遇到非表格行且已有資料，停止
                break
            continue
        if re.match(r"^\|\s*[:]+\s*\|", stripped):
            continue  # 分隔列 |:---:|
        if re.match(r"^\|\s*序號\s*\|", stripped):
            continue  # 表頭列
        if re.match(r"^\|\s*:---", stripped):
            continue
        rows.append(line)

    return rows


def _parse_rating_and_platform_from_row(clean_row: str) -> tuple[str, int]:
    """從已清除標籤的舊表格列中解析平台和評分。"""
    fields = _parse_row_fields(clean_row)
    if fields:
        return fields["platform"], fields["rating"]
    return "", 0


def _parse_date_from_row(clean_row: str) -> Optional[datetime]:
    """從表格列中解析日期時間。"""
    fields = _parse_row_fields(clean_row)
    return fields["date"] if fields else None


def _parse_config_date(value: str, *, end_of_day: bool = False) -> Optional[datetime]:
    """解析 YYYY-MM-DD 設定；空字串表示不限制。"""
    if not value:
        return None
    try:
        parsed_date = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        logger.warning(f"  ⚠️  日期設定格式錯誤：{value!r}，已忽略")
        return None

    parsed_time = time.max if end_of_day else time.min
    return datetime.combine(parsed_date, parsed_time, tzinfo=TW_TZ)


def _within_review_window(dt: datetime, start_date: Optional[datetime], end_date: Optional[datetime]) -> bool:
    """檢查評論日期是否落在設定範圍內。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TW_TZ)
    if start_date and dt < start_date:
        return False
    if end_date and dt > end_date:
        return False
    return True


# ── 主寫入函式 ────────────────────────────────────────────────

def update_md(
    md_path: str,
    app_name: str,
    new_reviews: list[Review],
    existing_keys: set[str],
) -> tuple[int, int, int]:
    """
    將新評論增量寫入 MD 檔案。

    Args:
        md_path:       MD 檔案路徑
        app_name:      App 名稱（顯示用）
        new_reviews:   本次抓到的所有評論（未過濾）
        existing_keys: 現有 MD 中已有的去重 key 集合

    Returns:
        (真正新增的 Google Play 數, App Store 數, 累計總則數)
    """
    path = Path(md_path)

    # 設定目標日期區間。結束日預設不限制，避免新評論被舊的分析截止日擋掉。
    start_date = _parse_config_date(config.REVIEW_START_DATE)
    end_date = _parse_config_date(config.REVIEW_END_DATE, end_of_day=True)
    window_label = (
        f"{config.REVIEW_START_DATE or '不限'} 至 "
        f"{config.REVIEW_END_DATE or '不限'}"
    )
    logger.info(f"  🗓  評論寫入日期範圍：{window_label}")

    # 1. 讀取現有 MD（若存在）取得舊評論列，先清洗既有重複並限制日期區間。
    existing_items = []
    existing_content_keys = set()
    existing_items_by_key = {}
    skipped_existing_dupes = 0
    if path.exists():
        old_content = path.read_text(encoding="utf-8")
        raw_existing_rows = _parse_existing_reviews_from_md(old_content)
        for old_row in raw_existing_rows:
            clean_row = _strip_red_tags(old_row)
            fields = _parse_row_fields(clean_row)
            if not fields or not _within_review_window(fields["date"], start_date, end_date):
                continue

            content_key = _row_content_key(clean_row)
            fallback_key = (
                f"{fields['platform']}|{fields['date'].strftime('%Y%m%d%H%M')}|"
                f"{fields['username'][:20].strip()}"
            )
            row_key = content_key or fallback_key
            if row_key in existing_content_keys:
                skipped_existing_dupes += 1
                continue
            existing_content_keys.add(row_key)
            item = {
                "date": fields["date"],
                "is_new": False,
                "clean_row_str": clean_row,
                "reply_text": fields.get("reply_text", ""),
            }
            existing_items.append(item)
            existing_items_by_key[row_key] = item
            existing_items_by_key[fallback_key] = item

    # 2. 準備新評論項目，限制在目標日期區間內，並做批內/跨來源內容去重。
    new_items = []
    seen_legacy_keys = set(existing_keys)
    seen_content_keys = set(existing_content_keys)
    skipped_new_dupes = 0
    updated_existing_replies = 0
    for r in new_reviews:
        if not _within_review_window(r.date, start_date, end_date):
            continue

        legacy_key = r.dedup_key()
        content_key = r.content_dedup_key()
        if legacy_key in seen_legacy_keys or content_key in seen_content_keys:
            skipped_new_dupes += 1
            reply = r.format_reply_for_md()
            existing_item = existing_items_by_key.get(content_key) or existing_items_by_key.get(legacy_key)
            if reply and existing_item and not existing_item.get("reply_text"):
                existing_item["reply_text"] = reply
                updated_existing_replies += 1
            continue

        seen_legacy_keys.add(legacy_key)
        seen_content_keys.add(content_key)
        new_items.append({
            "date": r.date,
            "is_new": True,
            "review": r
        })

    new_gplay = sum(1 for item in new_items if item["review"].platform == "Google Play")
    new_appstore = sum(1 for item in new_items if item["review"].platform == "App Store")

    if skipped_existing_dupes:
        logger.info(f"  🧹 已清除既有重複評論 {skipped_existing_dupes} 則")
    if skipped_new_dupes:
        logger.info(f"  🧹 已略過本批重複評論 {skipped_new_dupes} 則")
    if updated_existing_replies:
        logger.info(f"  💬 已補齊既有評論客服回覆 {updated_existing_replies} 則")

    if not new_items and not skipped_existing_dupes and not updated_existing_replies and path.exists():
        logger.info(f"  ✅ {path.name} 已是最新，無新評論可追加")
        return 0, 0, _count_existing_rows(path)

    logger.info(f"  ✨ 新增 {len(new_items)} 則評論（GP:{new_gplay} / AS:{new_appstore}）")

    # 3. 計算統計（用於摘要表，基於新+舊評論的評分）
    all_reviews_for_stats = []
    for item in new_items:
        all_reviews_for_stats.append(item["review"])
    for item in existing_items:
        platform, rating = _parse_rating_and_platform_from_row(item["clean_row_str"])
        if platform and rating:
            all_reviews_for_stats.append(Review(
                platform=platform,
                date=datetime.now(TW_TZ),
                username="",
                rating=rating,
                version="",
                title=None,
                content=""
            ))

    stats = _calc_stats(all_reviews_for_stats)
    total_count = len(new_items) + len(existing_items)

    # 4. 組裝統計區塊
    stats_rows = "\n".join([
        _stats_row("Google Play", stats["Google Play"]),
        _stats_row("App Store", stats["App Store"]),
        _stats_row("雙平台合併", stats["Combined"]),
    ])

    # 5. 合併所有評論，並按日期降序（新到舊）進行全局排序
    combined_items = new_items + existing_items
    combined_items.sort(key=lambda x: x["date"], reverse=True)

    # 6. 組裝評論列（全域重新編號 1 到 N）
    all_row_strings = []
    for idx, item in enumerate(combined_items, start=1):
        if item["is_new"]:
            all_row_strings.append(_format_row(idx, item["review"], is_red=False))
        else:
            # 歷史的評論：清除紅色標籤，顯示為常規顏色，並替換為新序號
            all_row_strings.append(_format_existing_row(idx, item))

    # 7. 組裝完整 MD
    last_updated = datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M")
    header = _MD_HEADER.format(
        app_name=app_name,
        last_updated=last_updated,
        new_count=len(new_items),
        new_gplay=new_gplay,
        new_appstore=new_appstore,
        total_count=total_count,
        stats_rows=stats_rows,
    )
    body = "\n".join(all_row_strings) + "\n"

    path.write_text(header + body, encoding="utf-8")
    logger.info(f"  💾 已儲存 {path.name}（累計 {total_count} 則）")

    return new_gplay, new_appstore, total_count


def backfill_appstore_replies(md_path: str, reply_rows: list[dict]) -> int:
    """用 App Store developerResponse 原始資料回填既有 MD 的空白客服回覆欄位。"""
    if not reply_rows:
        return 0

    path = Path(md_path)
    if not path.exists():
        return 0

    reply_by_key = {}
    for row in reply_rows:
        reply = _format_reply_text(row.get("replyBody", ""), row.get("replyModified", ""))
        if not reply:
            continue
        reply_by_key[_appstore_reply_row_key(row)] = reply

    if not reply_by_key:
        return 0

    lines = path.read_text(encoding="utf-8").splitlines()
    changed = 0
    updated_lines = []
    for line in lines:
        if not line.startswith("|"):
            updated_lines.append(line)
            continue

        fields = _parse_row_fields(_strip_red_tags(line))
        if not fields or fields["platform"] != "App Store" or fields.get("reply_text"):
            updated_lines.append(line)
            continue

        key = _appstore_reply_key(fields["username"], fields["rating"], fields["review_text"])
        reply = reply_by_key.get(key)
        if not reply:
            updated_lines.append(line)
            continue

        updated_lines.append(_replace_row_reply(line, reply))
        changed += 1

    if changed:
        path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
        logger.info(f"  💬 已直接回填 App Store 客服回覆 {changed} 則")

    return changed


def _count_existing_rows(path: Path) -> int:
    """計算現有 MD 中的評論列數。"""
    if not path.exists():
        return 0
    content = path.read_text(encoding="utf-8")
    return len(_parse_existing_reviews_from_md(content))
