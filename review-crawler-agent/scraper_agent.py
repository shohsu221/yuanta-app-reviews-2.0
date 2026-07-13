#!/usr/bin/env python3
"""
scraper_agent.py — 三大券商 App 評論爬蟲 Agent（主程式）

用法：
  python scraper_agent.py --run-now      # 立即執行一次
  python scraper_agent.py --schedule     # 進入排程模式（背景持續運行）
  python scraper_agent.py --find-ids     # 測試 App Store ID 自動偵測
"""

import argparse
import logging
import os
import shlex
import sys
import subprocess
import time
from datetime import datetime, timezone, timedelta

# ── 確保 agent/ 目錄在 Python path 中 ──────────────────────────
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

import config
import gplay_scraper
import appstore_scraper
import md_writer
import notifier
import web_sync
import validate_dashboard
import validate_reviews

# ── 日誌設定 ──────────────────────────────────────────────────
LOG_FILE = os.path.join(AGENT_DIR, "agent.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

TW_TZ = timezone(timedelta(hours=8))


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

    logger.info(f"  🔍 [{app['name']}] App Store ID 未設定，嘗試自動搜尋...")
    search_term = app.get("appstore_search_term", app["name"])
    found_id = appstore_scraper.find_appstore_id(search_term, country=config.COUNTRY)

    if found_id:
        config.save_appstore_id(app["short_name"], found_id)
        logger.info(f"  ✅ [{app['name']}] App Store ID 已快取：{found_id}")
        return found_id
    else:
        logger.error(f"  ❌ [{app['name']}] 無法自動取得 App Store ID，跳過 App Store 爬取")
        return None


def process_app(app: dict, fetch_count: int) -> tuple[int, int, int]:
    """
    處理單一 App：
    1. 取得現有 MD 的去重 key
    2. 分別爬取 Google Play 與 App Store
    3. 合併、去重、寫入 MD
    4. 發送 macOS 通知

    Returns:
        (new_gplay, new_appstore, total_count)
    """
    app_name = app["name"]
    md_path = app["output_file"]

    logger.info(f"\n{'='*60}")
    logger.info(f"▶  開始處理：{app_name}")
    logger.info(f"   MD 檔案：{os.path.basename(md_path)}")

    # Step 1: 讀取現有去重 Key
    existing_keys = md_writer.get_existing_keys(md_path)

    # Step 2: 爬取 Google Play
    gplay_reviews = gplay_scraper.fetch_reviews(
        app["gplay_id"], count=fetch_count
    )

    # Step 3: 爬取 App Store
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

    # Step 4: 合併所有新評論
    all_new_reviews = gplay_reviews + appstore_reviews

    if not all_new_reviews:
        logger.warning(f"  ⚠️  [{app_name}] 兩平台均無法取得評論")
        notifier.notify_error(app_name, "兩平台均無法取得評論")
        return 0, 0, md_writer._count_existing_rows(
            __import__("pathlib").Path(md_path)
        )

    # Step 5: 寫入 MD（去重 + 增量追加）
    new_gplay, new_appstore, total = md_writer.update_md(
        md_path=md_path,
        app_name=app_name,
        new_reviews=all_new_reviews,
        existing_keys=existing_keys,
    )

    if appstore_reply_rows:
        md_writer.backfill_appstore_replies(md_path, appstore_reply_rows)

    # Step 6: macOS 通知
    if new_gplay + new_appstore > 0:
        notifier.notify_success(app_name, new_gplay, new_appstore, total)
    else:
        notifier.notify_no_update(app_name)

    return new_gplay, new_appstore, total


def run_all(fetch_count: int = config.FETCH_COUNT):
    """執行所有 App 的評論更新。"""
    apps = config.get_apps()
    start_time = datetime.now(TW_TZ)

    logger.info(f"\n{'#'*60}")
    logger.info(f"🚀 評論爬蟲啟動 — {start_time.strftime('%Y-%m-%d %H:%M')} (台北時間)")
    logger.info(f"   共 {len(apps)} 個 App，每平台抓取最多 {fetch_count} 則")
    logger.info(f"{'#'*60}")

    notifier.notify_run_start(len(apps))

    total_new = 0
    results = []
    for app in apps:
        try:
            new_gplay, new_appstore, total = process_app(app, fetch_count)
            total_new += new_gplay + new_appstore
            results.append({
                "app": app["name"],
                "new_gplay": new_gplay,
                "new_appstore": new_appstore,
                "total": total,
            })
        except Exception as e:
            logger.exception(f"  ❌ [{app['name']}] 發生未預期錯誤：{e}")
            notifier.notify_error(app["name"], str(e))

    elapsed = (datetime.now(TW_TZ) - start_time).total_seconds()

    logger.info(f"\n{'#'*60}")
    logger.info("📊 執行摘要")
    logger.info(f"{'#'*60}")
    for r in results:
        logger.info(
            f"  {r['app']}: "
            f"新增 {r['new_gplay'] + r['new_appstore']} 則 "
            f"（GP {r['new_gplay']} / AS {r['new_appstore']}）"
            f" ｜ 累計 {r['total']} 則"
        )
    logger.info(f"  ⏱  耗時 {elapsed:.1f} 秒")
    logger.info(f"{'#'*60}\n")

    try:
        web_sync.sync_web_dashboard()
        validate_reviews.validate_no_duplicate_reviews()
        validate_dashboard.validate_dashboard()
    except Exception as e:
        logger.exception(f"  ❌ 資料驗證或首頁同步失敗：{e}")
        notifier.notify_error("資料驗證/首頁同步", str(e))
        raise

    notifier.notify_run_complete(total_new, len(apps))
    return total_new, results


def deploy_site() -> bool:
    """執行自動部署；支援環境變數指令或專案根目錄 deploy.sh。"""
    deploy_command = config.DEPLOY_COMMAND
    deploy_script = os.path.join(config.BASE_DIR, "deploy.sh")

    if deploy_command:
        cmd = shlex.split(deploy_command)
        logger.info(f"🚢 自動部署：執行 YUANTA_DEPLOY_COMMAND")
    elif os.path.isfile(deploy_script) and os.access(deploy_script, os.X_OK):
        cmd = [deploy_script]
        logger.info(f"🚢 自動部署：執行 {deploy_script}")
    else:
        logger.info(
            "🚢 自動部署略過：未設定 YUANTA_DEPLOY_COMMAND，且未找到可執行的 deploy.sh"
        )
        return False

    try:
        completed = subprocess.run(
            cmd,
            cwd=config.BASE_DIR,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ 自動部署失敗，exit code={e.returncode}")
        if e.stdout:
            logger.error(f"部署 stdout:\n{e.stdout.strip()}")
        if e.stderr:
            logger.error(f"部署 stderr:\n{e.stderr.strip()}")
        notifier.notify_error("自動部署", f"部署失敗：{e.returncode}")
        return False

    if completed.stdout.strip():
        logger.info(f"部署 stdout:\n{completed.stdout.strip()}")
    if completed.stderr.strip():
        logger.info(f"部署 stderr:\n{completed.stderr.strip()}")
    logger.info("✅ 自動部署完成")
    return True


# ══════════════════════════════════════════════════════════════
# 排程模式
# ══════════════════════════════════════════════════════════════

def run_scheduler():
    """
    排程模式：每週 config.SCHEDULE_DAY 的 config.SCHEDULE_TIME 執行。
    """
    try:
        import schedule
    except ImportError:
        logger.error("❌ 請先安裝 schedule 套件：pip install schedule")
        sys.exit(1)

    day_func = getattr(schedule.every(), config.SCHEDULE_DAY)
    day_func.at(config.SCHEDULE_TIME).do(run_all)

    logger.info(
        f"⏰ 排程已設定：每週{config.SCHEDULE_DAY} {config.SCHEDULE_TIME}（台北時間）"
    )
    logger.info("   （Ctrl+C 停止排程；或使用 macOS LaunchAgent 做系統層級排程）\n")

    while True:
        schedule.run_pending()
        time.sleep(30)  # 每 30 秒檢查一次是否到時間


# ══════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="三大券商 App 評論爬蟲 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  python scraper_agent.py --run-now            # 立即執行
  python scraper_agent.py --run-now --deploy   # 立即執行並部署
  python scraper_agent.py --run-now --count 200  # 每平台抓 200 則
  python scraper_agent.py --schedule           # 啟動排程（每週一 09:00）
  python scraper_agent.py --find-ids           # 測試 App Store ID 偵測
        """,
    )
    parser.add_argument(
        "--run-now", action="store_true",
        help="立即執行一次評論抓取",
    )
    parser.add_argument(
        "--schedule", action="store_true",
        help="啟動排程模式（每週自動執行）",
    )
    parser.add_argument(
        "--find-ids", action="store_true",
        help="測試 App Store ID 自動偵測功能",
    )
    parser.add_argument(
        "--count", type=int, default=config.FETCH_COUNT,
        help=f"每平台抓取的評論數（預設 {config.FETCH_COUNT}）",
    )
    parser.add_argument(
        "--deploy", action="store_true",
        help="爬取完成後執行自動部署",
    )
    parser.add_argument(
        "--no-deploy", action="store_true",
        help="即使設定了自動部署，也略過部署",
    )

    args = parser.parse_args()

    if args.find_ids:
        logger.info("🔍 測試 App Store ID 自動偵測…")
        for app in config.get_apps():
            logger.info(f"\n--- {app['name']} ---")
            resolve_appstore_id(app)
        return

    if args.run_now:
        run_all(fetch_count=args.count)
        should_deploy = args.deploy or (config.AUTO_DEPLOY and not args.no_deploy)
        if should_deploy:
            deploy_site()
        return

    if args.schedule:
        run_scheduler()
        return

    # 無引數時顯示說明
    parser.print_help()


if __name__ == "__main__":
    main()
