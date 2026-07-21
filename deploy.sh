#!/usr/bin/env bash
# deploy.sh — 部署「舊版」手作儀表板（根目錄 index.html / Yuanta_Reviews_Dashboard.html）
#
# 兩站已分開，互不影響：
#   舊版（本檔）       → yuanta-app-reviews-2.pages.dev   （已排除 site/ 與 analysis/）
#   新版 scikit-learn  → yuanta-app-reviews-ml.pages.dev  （見 deploy-site.sh）
#
# 預設部署到 Cloudflare Pages：
#   CLOUDFLARE_PROJECT_NAME=yuanta-app-reviews-2 ./deploy.sh
#
# 可用環境變數：
#   CLOUDFLARE_PROJECT_NAME  Cloudflare Pages 專案名稱，預設 yuanta-app-reviews-2
#   CLOUDFLARE_BRANCH        部署分支名稱，預設 main
#   YUANTA_DEPLOY_TARGET_DIR 若設定，改為同步到本機資料夾

set -euo pipefail

SITE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="${CLOUDFLARE_PROJECT_NAME:-yuanta-app-reviews-2}"
BRANCH="${CLOUDFLARE_BRANCH:-main}"
BUILD_DIR="${YUANTA_DEPLOY_BUILD_DIR:-/private/tmp/yuanta-app-reviews-2-pages}"

echo "=================================================="
echo "  Yuanta App Reviews 2.0 自動部署"
echo "  來源：$SITE_DIR"
echo "=================================================="

prepare_build_dir() {
    mkdir -p "$BUILD_DIR"
    rsync -av --delete --delete-excluded \
        --exclude 'crawler/' \
        --exclude '.wrangler/' \
        --exclude 'deploy.sh' \
        --exclude 'deploy-site.sh' \
        --exclude 'site/' \
        --exclude 'analysis/' \
        --exclude 'archive/' \
        --exclude '.gitignore' \
        --exclude '.DS_Store' \
        "$SITE_DIR/" "$BUILD_DIR/"
    echo "📦 靜態輸出：$BUILD_DIR"
}

if [ -n "${YUANTA_DEPLOY_TARGET_DIR:-}" ]; then
    prepare_build_dir
    mkdir -p "$YUANTA_DEPLOY_TARGET_DIR"
    rsync -av --delete "$BUILD_DIR/" "$YUANTA_DEPLOY_TARGET_DIR/"
    echo "✅ 已同步到：$YUANTA_DEPLOY_TARGET_DIR"
    exit 0
fi

prepare_build_dir

if command -v wrangler >/dev/null 2>&1; then
    WRANGLER=(wrangler)
elif command -v npx >/dev/null 2>&1; then
    WRANGLER=(npx wrangler)
else
    echo "❌ 找不到 wrangler 或 npx，無法部署 Cloudflare Pages" >&2
    echo "   請安裝 wrangler，或設定 YUANTA_DEPLOY_TARGET_DIR 改為同步到本機目錄。" >&2
    exit 127
fi

deploy_log="/private/tmp/yuanta-app-reviews-2-deploy.log"
if ! "${WRANGLER[@]}" pages deploy "$BUILD_DIR" \
    --project-name "$PROJECT_NAME" \
    --branch "$BRANCH" \
    --commit-dirty=true 2>&1 | tee "$deploy_log"; then
    if grep -q "Project not found" "$deploy_log"; then
        echo "ℹ️  Cloudflare Pages 專案不存在，正在建立：$PROJECT_NAME"
        "${WRANGLER[@]}" pages project create "$PROJECT_NAME" \
            --production-branch "$BRANCH"
        "${WRANGLER[@]}" pages deploy "$BUILD_DIR" \
            --project-name "$PROJECT_NAME" \
            --branch "$BRANCH" \
            --commit-dirty=true
    else
        exit 1
    fi
fi

echo "✅ Cloudflare Pages 部署完成：$PROJECT_NAME / $BRANCH"
