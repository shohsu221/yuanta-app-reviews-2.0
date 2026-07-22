#!/usr/bin/env python3
"""
main.py — 三大券商 App 評論爬蟲系統主入口與任務協調器

負責處理使用者 CLI 指令、定時排程、調用爬蟲引擎、同步網頁指標、執行去重驗證以及自動部署。
"""

import argparse
import logging
import os
import shlex
import sys
import subprocess
import time
from datetime import datetime, timezone, timedelta

# ── 確保 crawler 目錄在 Python path 中 ──────────────────────────
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CRAWLER_DIR = os.path.join(ROOT_DIR, "crawler")
if CRAWLER_DIR not in sys.path:
    sys.path.insert(0, CRAWLER_DIR)

from crawler.utils import config, notifier
from crawler import crawler_runner
from crawler.sync import web_sync
from crawler.validation import validate_reviews, validate_dashboard

# 確保 Windows 終端機能支援 UTF-8 輸出
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ── 日誌設定 ──────────────────────────────────────────────────
LOG_FILE = os.path.join(CRAWLER_DIR, "agent.log")

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


def run_crawler(fetch_count: int = config.FETCH_COUNT) -> tuple[int, list]:
    """爬取所有 App 的雙平台最新評論並更新資料庫。"""
    apps = config.get_apps()
    total_new = 0
    start_time = time.time()

    # 台北時間
    now_tw = datetime.now(timezone.utc).astimezone(TW_TZ)
    now_str = now_tw.strftime("%Y-%m-%d %H:%M")

    logger.info("\n" + "#" * 60)
    logger.info(f"評論爬蟲啟動 — {now_str} (台北時間)")
    logger.info(f"   共 {len(apps)} 個 App，每平台抓取最多 {fetch_count} 則")
    logger.info("#" * 60)

    app_results = []
    for app in apps:
        try:
            # 呼叫爬蟲引擎爬取各 App 並更新資料庫
            new_gp, new_as, total = crawler_runner.process_app(app, fetch_count)
            total_new += new_gp + new_as
            app_results.append((app["name"], new_gp, new_as, total))
        except Exception as e:
            logger.exception(f"處理 [{app['name']}] 時發生未預期錯誤")

    elapsed = time.time() - start_time

    # 印出總結摘要
    logger.info("\n" + "#" * 60)
    logger.info("執行摘要")
    logger.info("#" * 60)
    for name, gp, as_, total in app_results:
        logger.info(f"  {name}: 新增 {gp+as_} 則 （GP {gp} / AS {as_}） ｜ 累計 {total} 則")
    logger.info(f"耗時 {elapsed:.1f} 秒")
    logger.info("#" * 60 + "\n")

    # 傳送摘要通知
    notifier.notify_run_complete(total_new, len(apps))

    return total_new, app_results


def sync_dashboard():
    """同步 JSON 資料庫統計指標至 HTML 網頁。"""
    logger.info("開始同步網頁儀表板數據...")
    web_sync.sync_web_dashboard()
    logger.info("網頁儀表板數據同步完成。")


def validate_web_dashboard():
    """驗證 HTML 儀表板中的數據與 JSON 資料庫一致，防止錯誤數據被部署。"""
    logger.info("開始驗證網頁儀表板數據...")
    try:
        validate_dashboard.validate_dashboard()
        logger.info("網頁儀表板數據驗證通過。")
    except Exception as e:
        logger.exception(f"網頁儀表板數據驗證失敗：{e}")
        notifier.notify_error("儀表板驗證", str(e))
        raise


def validate_data():
    """執行資料庫的重複資料去重校驗。"""
    logger.info("開始執行評論資料庫去重校驗...")
    try:
        validate_reviews.validate_no_duplicate_reviews()
        logger.info("資料去重校驗成功通關！")
    except Exception as e:
        logger.exception(f"資料校驗同步失敗：{e}")
        notifier.notify_error("資料校驗", str(e))
        raise


def deploy_site():
    """
    自動執行雲端部署指令或指令檔。
    這通常被用在 Github Pages / Cloudflare Pages 發布更新。
    """
    deploy_command = config.DEPLOY_COMMAND
    deploy_script = os.path.join(config.BASE_DIR, "deploy", "deploy.sh")

    if deploy_command:
        cmd = shlex.split(deploy_command)
        logger.info(f"自動部署：執行 YUANTA_DEPLOY_COMMAND")
    elif os.path.isfile(deploy_script):
        cmd = [deploy_script]
        logger.info(f"自動部署：執行 {deploy_script}")
    else:
        logger.info(
            "自動部署略過：未設定 YUANTA_DEPLOY_COMMAND，且未找到可執行的 deploy/deploy.sh"
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
        logger.error(f"自動部署失敗，exit code={e.returncode}")
        if e.stdout:
            logger.error(f"部署 stdout:\n{e.stdout.strip()}")
        if e.stderr:
            logger.error(f"部署 stderr:\n{e.stderr.strip()}")
        notifier.notify_error("自動部署", f"部署失敗：{e.returncode}")
        return False
    except OSError as e:
        logger.warning(f"自動部署無法在本機執行 (Windows 環境無原生 Bash 支持)：{e}")
        return False

    if completed.stdout.strip():
        logger.info(f"部署 stdout:\n{completed.stdout.strip()}")
    if completed.stderr.strip():
        logger.info(f"部署 stderr:\n{completed.stderr.strip()}")
    logger.info("自動部署完成")
    return True


def run_all(fetch_count: int = config.FETCH_COUNT, deploy: bool = False, no_deploy: bool = False):
    """循序執行完整的評論抓取、同步、校驗與自動部署工作流。"""
    # 1. 執行爬取
    run_crawler(fetch_count=fetch_count)
    # 2. 同步網頁
    sync_dashboard()
    # 3. 驗證 HTML 儀表板數據
    validate_web_dashboard()
    # 4. 驗證資料庫去重
    validate_data()
    # 5. 自動部署
    should_deploy = deploy or (config.AUTO_DEPLOY and not no_deploy)
    if should_deploy:
        deploy_site()


def run_scheduler(fetch_count: int, deploy: bool, no_deploy: bool):
    """
    排程模式：每週 config.SCHEDULE_DAY 的 config.SCHEDULE_TIME 執行定時工作流。
    """
    try:
        import schedule
    except ImportError:
        logger.error("請先安裝 schedule 套件：pip install schedule")
        sys.exit(1)

    day_func = getattr(schedule.every(), config.SCHEDULE_DAY)
    day_func.at(config.SCHEDULE_TIME).do(
        run_all, fetch_count=fetch_count, deploy=deploy, no_deploy=no_deploy
    )

    logger.info(
        f"排程已設定：每週{config.SCHEDULE_DAY} {config.SCHEDULE_TIME}（台北時間）"
    )
    logger.info("   （Ctrl+C 停止排程；或使用 macOS LaunchAgent 做系統層級排程）\n")

    while True:
        schedule.run_pending()
        time.sleep(30)  # 每 30 秒檢查一次是否到時間


def main():
    # 建立引數解析器，定義 CLI 呼叫的各項指令參數與說明範例
    parser = argparse.ArgumentParser(
        description="三大券商 App 評論爬蟲主控制器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            範例：
            python main.py --run-now            # 立即執行完整工作流
            python main.py --crawler --count 5  # 僅執行爬蟲抓取 5 則
            python main.py --sync               # 僅同步數據至網頁
            python main.py --validate           # 僅執行資料庫去重校驗
            python main.py --deploy             # 僅執行網站部署
            python main.py --schedule           # 啟動定時排程（背景執行）
        """,
    )
    # --run-now：指示系統立即啟動抓取與更新流程一次
    parser.add_argument(
        "--run-now", action="store_true",
        help="立即執行完整評論更新工作流",
    )
    # --schedule：進入背景循環模式，根據設定檔中的時間定時重複執行爬取工作
    parser.add_argument(
        "--schedule", action="store_true",
        help="啟動定時排程模式（背景持續運行）",
    )
    # --find-ids：測試 iTunes Search API 能否正確搜尋到 App Store ID 並寫入暫存
    parser.add_argument(
        "--find-ids", action="store_true",
        help="測試 App Store ID 自動偵測功能",
    )
    # --count：限制單次抓取的評論上限數量，避免被商店伺服器封鎖
    parser.add_argument(
        "--count", type=int, default=config.FETCH_COUNT,
        help=f"每平台抓取的評論數（預設 {config.FETCH_COUNT}）",
    )
    # --deploy：指示流程結束後，強制觸發部署指令檔（忽略設定檔中的自動部署開關）
    parser.add_argument(
        "--deploy", action="store_true",
        help="強制執行自動部署",
    )
    # --no-deploy：用以暫時覆寫並停用部署動作，即使設定檔預設開啟了自動部署
    parser.add_argument(
        "--no-deploy", action="store_true",
        help="即使設定了自動部署，也略過部署",
    )
    # ── 單模組測試引數 ──────────────────────────────────────────────
    parser.add_argument(
        "--crawler", action="store_true",
        help="僅執行評論抓取與資料庫更新",
    )
    parser.add_argument(
        "--sync", action="store_true",
        help="僅執行資料同步至網頁儀表板",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="僅執行評論資料庫重複校驗",
    )

    args = parser.parse_args()

    # 處理 --find-ids 分支：執行 App Store ID 自適應偵測
    if args.find_ids:
        logger.info("[偵測] 測試 App Store ID 自動偵測...")
        for app in config.get_apps():
            logger.info(f"\n--- {app['name']} ---")
            crawler_runner.resolve_appstore_id(app)
        return

    # 單模組操作（可組合使用，例如 --crawler --sync）
    # 若搜配 --run-now，--deploy 由下方 run_all() 統一處理
    has_action = False
    if args.crawler:
        run_crawler(fetch_count=args.count)
        has_action = True
    if args.sync:
        sync_dashboard()
        has_action = True
    if args.validate:
        validate_data()
        has_action = True
    if args.deploy and not args.run_now:
        # 單獨傳入 --deploy（不含 --run-now）時，直接觸發部署
        deploy_site()
        has_action = True

    if has_action:
        return

    # 處理 --run-now 分支：立即執行完整工作流
    if args.run_now:
        run_all(fetch_count=args.count, deploy=args.deploy, no_deploy=args.no_deploy)
    # 處理 --schedule 分支：啟動背景自動排程監聽器
    elif args.schedule:
        run_scheduler(fetch_count=args.count, deploy=args.deploy, no_deploy=args.no_deploy)
    # 無輸入任何執行參數時，預設列出說明指南
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
