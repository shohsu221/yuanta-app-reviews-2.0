#!/usr/bin/env bash
# deploy-site.sh — 部署「新版」scikit-learn 管線儀表板（site/）到獨立的 Cloudflare Pages 專案
#
# 兩站已分開，互不影響：
#   舊版手作儀表板     → yuanta-app-reviews-2.pages.dev   （見 deploy.sh）
#   新版（本檔）       → yuanta-app-reviews-ml.pages.dev
#
# 部署前請先重建頁面：  ../.venv-ioscrawl311/bin/python3 analysis/build_site.py --fresh
#
# 可用環境變數：
#   CLOUDFLARE_PROJECT_NAME  Pages 專案名稱，預設 yuanta-app-reviews-ml
#   CLOUDFLARE_BRANCH        部署分支，預設 main

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SITE_DIR="$ROOT_DIR/site"
PROJECT_NAME="${CLOUDFLARE_PROJECT_NAME:-yuanta-app-reviews-ml}"
BRANCH="${CLOUDFLARE_BRANCH:-main}"

echo "=================================================="
echo "  新版分析儀表板部署（scikit-learn 管線）"
echo "  來源：$SITE_DIR"
echo "  專案：$PROJECT_NAME / $BRANCH"
echo "=================================================="

if [ ! -f "$SITE_DIR/index.html" ]; then
    echo "❌ 找不到 $SITE_DIR/index.html，請先執行 analysis/build_site.py --fresh" >&2
    exit 1
fi

if command -v wrangler >/dev/null 2>&1; then
    WRANGLER=(wrangler)
elif command -v npx >/dev/null 2>&1; then
    WRANGLER=(npx wrangler)
else
    echo "❌ 找不到 wrangler 或 npx，無法部署 Cloudflare Pages" >&2
    exit 127
fi

deploy_log="/private/tmp/${PROJECT_NAME}-deploy.log"
if ! "${WRANGLER[@]}" pages deploy "$SITE_DIR" \
    --project-name "$PROJECT_NAME" \
    --branch "$BRANCH" \
    --commit-dirty=true 2>&1 | tee "$deploy_log"; then
    if grep -q "Project not found" "$deploy_log"; then
        echo "ℹ️  Cloudflare Pages 專案不存在，正在建立：$PROJECT_NAME"
        "${WRANGLER[@]}" pages project create "$PROJECT_NAME" \
            --production-branch "$BRANCH"
        "${WRANGLER[@]}" pages deploy "$SITE_DIR" \
            --project-name "$PROJECT_NAME" \
            --branch "$BRANCH" \
            --commit-dirty=true
    else
        exit 1
    fi
fi

echo "✅ 新版部署完成：$PROJECT_NAME / $BRANCH"
