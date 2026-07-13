#!/usr/bin/env bash
# run_agent.sh — 一鍵啟動評論爬蟲（自動建立 venv）
#
# 用法：
#   ./run_agent.sh              → 立即執行一次
#   ./run_agent.sh --no-deploy  → 立即執行一次，但略過自動部署
#   ./run_agent.sh --schedule   → 進入排程模式（背景執行，週一 09:00 自動觸發）
#   ./run_agent.sh --find-ids   → 測試 App Store ID 偵測
#   ./run_agent.sh --count 200  → 立即執行，每平台抓 200 則

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
AGENT_SCRIPT="$SCRIPT_DIR/scraper_agent.py"

echo "=================================================="
echo "  三大券商 App 評論爬蟲 Agent"
echo "  工作目錄：$SCRIPT_DIR"
echo "  自動部署：預設啟用（可用 --no-deploy 或 YUANTA_AUTO_DEPLOY=0 關閉）"
echo "=================================================="

# ── 建立 / 驗證 Python 虛擬環境 ──────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 建立 Python 虛擬環境..."
    python3 -m venv "$VENV_DIR"
fi

# 啟動虛擬環境
source "$VENV_DIR/bin/activate"

# ── 安裝 / 更新依賴套件 ───────────────────────────────────────
echo "📥 確認依賴套件..."
pip install -q -r "$REQUIREMENTS"

# ── 執行 Agent ────────────────────────────────────────────────
echo ""

# 解析傳入的參數
ARGS=("$@")
if [ ${#ARGS[@]} -eq 0 ]; then
    # 無引數 → 立即執行一次
    echo "▶  立即執行模式（--run-now）"
    python3 "$AGENT_SCRIPT" --run-now
else
    echo "▶  執行：python3 scraper_agent.py ${ARGS[*]}"
    python3 "$AGENT_SCRIPT" "${ARGS[@]}"
fi
