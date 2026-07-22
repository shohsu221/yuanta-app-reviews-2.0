#!/usr/bin/env bash
# setup_launchagent.sh — 一鍵安裝 macOS LaunchAgent（週一 09:00 自動執行）
#
# 執行後，每週一早上 09:00 系統將自動觸發評論爬蟲，
# 完成後自動部署並發送 macOS 桌面通知。
#
# 用法：
#   ./setup_launchagent.sh          → 安裝/更新 LaunchAgent
#   ./setup_launchagent.sh unload   → 停用 LaunchAgent
#   ./setup_launchagent.sh status   → 查看狀態

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_TEMPLATE="$SCRIPT_DIR/com.yuanta.review-crawler-agent.plist"
PLIST_LABEL="com.yuanta.review-crawler-agent"
PLIST_DEST="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
LAUNCH_DOMAIN="gui/$(id -u)"
LAUNCH_SERVICE="${LAUNCH_DOMAIN}/${PLIST_LABEL}"

ACTION="${1:-install}"

# ── 先確認 venv 存在 ──────────────────────────────────────────
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "📦 尚未建立虛擬環境，先執行一次 run_agent.sh..."
    bash "$SCRIPT_DIR/run_agent.sh" --help || true
fi

# ── 狀態查詢 ─────────────────────────────────────────────────
if [ "$ACTION" = "status" ]; then
    echo "📋 LaunchAgent 狀態："
    if launchctl print "$LAUNCH_SERVICE" >/dev/null 2>&1; then
        launchctl print "$LAUNCH_SERVICE" | sed -n \
            -e '1,8p' \
            -e '/arguments = {/,/}/p' \
            -e '/event triggers = {/,/event channels = {/p'
    else
        echo "  （未載入）"
    fi
    exit 0
fi

# ── 停用 ─────────────────────────────────────────────────────
if [ "$ACTION" = "unload" ]; then
    echo "⏹  停用 LaunchAgent..."
    launchctl bootout "$LAUNCH_DOMAIN" "$PLIST_DEST" 2>/dev/null || true
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    rm -f "$PLIST_DEST"
    echo "✅ LaunchAgent 已停用並移除"
    exit 0
fi

# ── 安裝 ─────────────────────────────────────────────────────
echo "=================================================="
echo "  安裝 macOS LaunchAgent"
echo "  排程：每週一 09:00（台北時間）"
echo "  目標：$PLIST_DEST"
echo "=================================================="

mkdir -p "$HOME/Library/LaunchAgents"

# 將 plist 模板中的 AGENT_DIR 替換為實際路徑
sed "s|AGENT_DIR|$SCRIPT_DIR|g" "$PLIST_TEMPLATE" > "$PLIST_DEST"

echo "✏️  已生成 plist：$PLIST_DEST"

# 若已載入，先卸載
launchctl bootout "$LAUNCH_DOMAIN" "$PLIST_DEST" 2>/dev/null || true
launchctl unload "$PLIST_DEST" 2>/dev/null || true

# 載入 LaunchAgent
if ! launchctl bootstrap "$LAUNCH_DOMAIN" "$PLIST_DEST" 2>/dev/null; then
    # 舊版 macOS fallback
    launchctl load "$PLIST_DEST"
fi

echo ""
echo "✅ LaunchAgent 安裝完成！"
echo ""
echo "📅 排程：每週一 09:00 自動執行爬蟲"
echo "🚢 部署：爬取完成後自動執行 ../deploy.sh"
echo "📂 Log：$SCRIPT_DIR/agent.log"
echo "🔔 完成後將發送 macOS 桌面通知"
echo ""
echo "其他指令："
echo "  ./setup_launchagent.sh status  → 查看狀態"
echo "  ./setup_launchagent.sh unload  → 停用排程"
echo "  ./run_agent.sh                 → 立即手動執行一次"
