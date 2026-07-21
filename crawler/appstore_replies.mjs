/**
 * appstore_replies.mjs — 透過無頭瀏覽器抓取 App Store 評論與「開發者回覆」。
 *
 * Apple 已把媒體 API 改為以 cookie/session 授權的 `apps.apple.com/api/...` 代理，
 * 不再於頁面或 JS bundle 中暴露 Bearer token。因此用 Playwright 載入 App 頁面取得
 * session cookie 後，於頁面情境內 fetch reviews 端點即可取得含 developerResponse 的資料。
 *
 * 用法：
 *   node appstore_replies.mjs <appId> [country] [count]
 * 輸出（stdout）：JSON 陣列，每筆為
 *   { userName, rating, title, review, date, replyBody, replyModified }
 *
 * 失敗時以非零 exit code 結束，並把錯誤寫到 stderr；呼叫端應優雅降級（略過回覆）。
 */

import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import path from 'node:path';

const appId = process.argv[2];
const country = process.argv[3] || 'tw';
const count = parseInt(process.argv[4] || '100', 10);

if (!appId) {
  console.error('usage: node appstore_replies.mjs <appId> [country] [count]');
  process.exit(2);
}

// ── 定位 playwright 模組（本專案未安裝，沿用系統既有安裝） ──────────────
function resolvePlaywright() {
  const require = createRequire(import.meta.url);
  // 1) 一般解析（若專案/全域有安裝）
  try { return require.resolve('playwright'); } catch {}
  // 2) 常見安裝位置備援
  const candidates = [
    path.join(homedir(), '.claude/skills/gstack/node_modules/playwright'),
    path.join(homedir(), '.npm/_npx'),
  ];
  for (const base of candidates) {
    const direct = path.join(base, 'index.js');
    if (existsSync(direct)) return direct;
    const pkg = path.join(base, 'package.json');
    if (existsSync(pkg)) return base;
  }
  return null;
}

const pwPath = resolvePlaywright();
if (!pwPath) {
  console.error('playwright module not found');
  process.exit(3);
}

// 若呼叫端未設定瀏覽器路徑，補上預設快取位置
if (!process.env.PLAYWRIGHT_BROWSERS_PATH) {
  const cache = path.join(homedir(), 'Library/Caches/ms-playwright');
  if (existsSync(cache)) process.env.PLAYWRIGHT_BROWSERS_PATH = cache;
}

const mod = await import(pathToFileURL(pwPath).href);
const chromium = mod.chromium || (mod.default && mod.default.chromium);
if (!chromium) {
  console.error('chromium launcher not found in playwright module');
  process.exit(3);
}

const lang = country === 'tw' ? 'zh-TW' : 'en-US';

const browser = await chromium.launch({ headless: true });
let out = [];
try {
  const page = await browser.newPage({ locale: lang });
  // 載入 App 頁面以取得 session cookie
  await page.goto(`https://apps.apple.com/${country}/app/id${appId}`, {
    waitUntil: 'domcontentloaded', timeout: 45000,
  }).catch(() => {});
  await page.waitForTimeout(1500);

  // 於頁面情境內以 cookie 授權呼叫 reviews 端點，逐頁取回
  out = await page.evaluate(async ({ appId, country, lang, count }) => {
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    const results = [];
    const limit = 20;
    const makeUrl = (offset) => `https://apps.apple.com/api/apps/v1/catalog/${country}/apps/${appId}/reviews`
      + `?l=${lang}&offset=${offset}&limit=${limit}&platform=web&additionalPlatforms=appletv,ipad,iphone,mac`;
    let offset = 0;
    let url = makeUrl(offset);
    let guard = 0;
    while (url && results.length < count && guard < 40) {
      guard++;
      let resp;
      try { resp = await fetch(url, { headers: { accept: 'application/json' } }); }
      catch { break; }
      if (resp.status === 429) { await sleep(15000); continue; }
      if (resp.status !== 200) break;
      let j;
      try { j = await resp.json(); } catch { break; }
      const entries = j.data || [];
      if (!entries.length) break;
      for (const e of entries) {
        if (results.length >= count) break;
        const a = e.attributes || {};
        const dr = a.developerResponse;
        results.push({
          userName: a.userName || '',
          rating: a.rating || 0,
          title: a.title || '',
          review: a.review || '',
          date: a.date || '',
          replyBody: dr ? (dr.body || '') : '',
          replyModified: dr ? (dr.modified || '') : '',
        });
      }
      let next = j.next || null;
      if (next && !next.startsWith('http')) next = 'https://apps.apple.com' + next;
      // 把舊式 /v1/ 路徑轉成新的 cookie 代理 /api/apps/v1/
      if (next) next = next.replace('apps.apple.com/v1/', 'apps.apple.com/api/apps/v1/');
      if (next) {
        url = next;
      } else {
        offset += limit;
        url = makeUrl(offset);
      }
      await sleep(150);
    }
    return results;
  }, { appId, country, lang, count });
} finally {
  await browser.close();
}

process.stdout.write(JSON.stringify(out));
