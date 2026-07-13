"""
config.py — 爬蟲 Agent 全域設定
"""
import os
import json

# ── 路徑設定 ──────────────────────────────────────────────────
# agent/ 的上一層，即 "Yuanta App Reviews/" 資料夾
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

# App Store ID 快取（自動偵測後儲存）
IDS_CACHE_FILE = os.path.join(AGENT_DIR, ".appstore_ids_cache.json")

# ── 爬蟲設定 ─────────────────────────────────────────────────
# 每次爬取的最新評論數（雙平台各自抓取 N 則，取其中最新且未出現在 MD 的）
FETCH_COUNT = 100

# 評論寫入日期範圍。
# 預設保留 2026 年起的所有評論，不設定結束日，避免新月份評論被固定截止日擋掉。
REVIEW_START_DATE = os.getenv("YUANTA_REVIEW_START_DATE", "2026-01-01")
REVIEW_END_DATE = os.getenv("YUANTA_REVIEW_END_DATE", "")

# 自動部署設定：
# 1. 若設定 YUANTA_DEPLOY_COMMAND，爬取完成後會執行該指令。
# 2. 若未設定但 BASE_DIR/deploy.sh 存在且可執行，會執行 deploy.sh。
# 3. 若都沒有，會略過部署並寫入 log。
DEPLOY_COMMAND = os.getenv("YUANTA_DEPLOY_COMMAND", "").strip()
AUTO_DEPLOY = os.getenv("YUANTA_AUTO_DEPLOY", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}

# App Store 國家碼 & 語系
COUNTRY = "tw"
LANGUAGE = "zh_TW"

# ── 排程設定 ─────────────────────────────────────────────────
# 每週幾（weekday：monday / tuesday / ... / sunday）
SCHEDULE_DAY = "monday"
# 每週幾點執行（24 小時制，台北時間）
SCHEDULE_TIME = "09:00"

# ── 三大 App 設定 ────────────────────────────────────────────

def _load_id_cache() -> dict:
    """讀取 App Store ID 快取。"""
    if os.path.exists(IDS_CACHE_FILE):
        try:
            with open(IDS_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_id_cache(cache: dict):
    """儲存 App Store ID 快取。"""
    with open(IDS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

# 底層 App 設定（appstore_id 為 "AUTO" 表示首次執行時自動搜尋）
_APP_CONFIGS_BASE = [
    {
        "name": "元大投資先生",
        "short_name": "Yuanta",
        "gplay_id": "com.yuanta.android.nexus",  # 已確認：投資先生 App
        "appstore_id": "1382114621",              # 已確認
        "appstore_search_term": "投資先生 元大",
        "output_file": os.path.join(BASE_DIR, "Yuanta_App_Reviews.md"),
    },
    {
        "name": "永豐大戶投",
        "short_name": "SinoPac",
        "gplay_id": "com.sinopac.ismartstock",
        "appstore_id": "1551600164",       # 已確認：永豐金證券大戶投 – 智能籌碼權威升級
        "appstore_search_term": "永豐金證券大戶投",
        "output_file": os.path.join(BASE_DIR, "SinoPac_App_Reviews.md"),
    },
    {
        "name": "國泰證券",
        "short_name": "Cathay",
        "gplay_id": "com.cathaysec.eservice",
        "appstore_id": "1228503534",       # 已確認
        "appstore_search_term": "國泰證券",
        "output_file": os.path.join(BASE_DIR, "Cathay_App_Reviews.md"),
    },
]

def get_apps() -> list[dict]:
    """
    回傳 App 設定清單。
    若 appstore_id 為 'AUTO'，從快取讀取；快取不存在則保留 'AUTO'，
    待 scraper_agent 在首次執行時自動偵測並寫入快取。
    """
    cache = _load_id_cache()
    apps = []
    for cfg in _APP_CONFIGS_BASE:
        app = dict(cfg)
        if app["appstore_id"] == "AUTO":
            cached_id = cache.get(app["short_name"])
            if cached_id:
                app["appstore_id"] = cached_id
        apps.append(app)
    return apps

def save_appstore_id(short_name: str, app_id: str):
    """將自動偵測到的 App Store ID 寫入快取。"""
    cache = _load_id_cache()
    cache[short_name] = app_id
    _save_id_cache(cache)
