"""
notifier.py — macOS 桌面通知（透過 osascript，無需額外套件）
"""
import subprocess
import logging

logger = logging.getLogger(__name__)


def notify(title: str, message: str, subtitle: str = ""):
    """
    發送 macOS 桌面通知。

    Args:
        title:    通知標題（大字）
        message:  通知內文
        subtitle: 副標題（可選）
    """
    # 轉義雙引號以避免 AppleScript 語法錯誤
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    parts = [f'display notification "{esc(message)}" with title "{esc(title)}"']
    if subtitle:
        parts.append(f'subtitle "{esc(subtitle)}"')

    script = " ".join(parts)

    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
        )
        logger.debug(f"  🔔 通知已發送：{title}")
    except subprocess.CalledProcessError as e:
        logger.warning(f"  ⚠️  macOS 通知發送失敗：{e.stderr.decode()}")
    except FileNotFoundError:
        logger.warning("  ⚠️  osascript 未找到（僅 macOS 支援通知功能）")


# ── 預設通知模板 ──────────────────────────────────────────────

def notify_success(app_name: str, new_gplay: int, new_appstore: int, total: int):
    """執行成功，有新評論時的通知。"""
    notify(
        title="📊 評論更新完成",
        subtitle=app_name,
        message=(
            f"新增 {new_gplay + new_appstore} 則"
            f"（Play {new_gplay} ／ AS {new_appstore}）"
            f"｜累計 {total} 則"
        ),
    )


def notify_no_update(app_name: str):
    """無新評論時的通知。"""
    notify(
        title="✅ 評論已是最新",
        subtitle=app_name,
        message="本週無新評論，MD 檔案維持不變",
    )


def notify_error(app_name: str, error: str):
    """發生錯誤時的通知。"""
    notify(
        title="❌ 評論抓取失敗",
        subtitle=app_name,
        message=f"錯誤：{error[:80]}",
    )


def notify_run_start(app_count: int):
    """整批開始執行時的通知。"""
    notify(
        title="🤖 評論爬蟲啟動",
        message=f"開始更新 {app_count} 個 App 的評論資料…",
    )


def notify_run_complete(total_new: int, app_count: int):
    """整批完成時的摘要通知。"""
    if total_new > 0:
        notify(
            title="🎉 本週評論更新完成",
            message=f"共 {app_count} 個 App，新增 {total_new} 則評論",
        )
    else:
        notify(
            title="✅ 本週評論已是最新",
            message=f"共 {app_count} 個 App，均無新評論",
        )
