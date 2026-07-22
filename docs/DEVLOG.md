# Yuanta Reviews Dashboard — DEVLOG

Development log for **`Yuanta_Reviews_Web.html`** (formerly `Yuanta_Reviews_Dashboard_B2.html`) —
a from-scratch rebuild of the 元大投資先生 App reviews dashboard in a clean Apple design language
("B2" direction). This is now **the single source of truth and the deployed site**; the older
dashboards live in `archive/` and are excluded from deploy.
Keep this file updated as the dashboard evolves.

Last updated: 2026-07-01

---

## 1. What this is

A single-file, dependency-light analytics dashboard comparing three Taiwanese brokerage apps
(元大投資先生 / 永豐大戶投 / 國泰證券) across Google Play + App Store reviews for 2026 Q1–Q2.

- **Period:** 2026 Q1–Q2, review data auto-refreshed weekly (see §4).
- **Sample:** ~1,257 reviews as of 2026-07-01 (元大 413 · 永豐 405 · 國泰 439) — grows each weekly crawl.
- Three tabs: `數據全景分析` (analytics) · `詳細用戶評論` (review browser) · `專家聯席戰略分析` (locked)

### File map
| File | Role |
|---|---|
| `Yuanta_Reviews_Web.html` | **The current dashboard — source of truth & deployed site.** All work below lives here. Served at `/` via `_redirects`. |
| `archive/Yuanta_Reviews_Dashboard.html` | Original dashboard (archived). Source of truth for the review data. Not deployed. |
| `archive/index.html` | Old root page / Phosphor icon reference (archived). Not deployed. |

---

## 2. Status

Shippable and **live**, auto-refreshed weekly. Data fidelity verified by an independent full-page
audit — all 87 structured numbers match the review `.md` data (see §4).
No blocking console errors. Responsive at 390 / 768 / 1280. Open `Yuanta_Reviews_Web.html` directly in a browser.

Outstanding work is in §6.

---

## 3. Design system (Apple)

Tokens come from the open-design Apple design system. All values live in the first `<style>` `:root`.

- **Surfaces:** page `--surface:#f5f5f7` · card `--card:#fff` · nested panel `--panel:#f1f2f5`
- **Ink ramp:** `#1d1d1f` / `#424245` / `--muted:#6e6e73` / `--meta:#86868b`
- **Borders:** `--border:#d2d2d7` / `--border-soft:#e8e8ed` (used sparingly — see §5)
- **Single accent:** Apple blue `--accent:#0071e3` (hover `#0077ed`, active `#0066cc`). One accent only.
- **Brand data colors:** 元大 `#0071e3` (blue) · 永豐 `#bf7a12` (amber) · 國泰 `#c8324f` (rose)
- **Cathay green exception:** 國泰 **brand tags** use Cathay green `#00684c` (class `.tgc`, hero pill `.pc`).
  國泰 **score card / competitor card / severity warnings** stay rose. (See §5 note.)
- **Type:** SF Pro Display (headings, `--fd`) + SF Pro Text (body, `--f`) + Noto Sans TC for CJK.
  Weights: 600 dominant, 700 selective — never 900.
- **Motion:** Apple easing `--ease:cubic-bezier(.28,0,.22,1)`.
- **Elevation:** `--elev` / `--elev-hover` (cards lift by shadow, not borders).
- **Icons:** Phosphor (`<script src="https://unpkg.com/@phosphor-icons/web">`), `ph-bold` weight.
- **Charts:** Chart.js 4.4.1 (CDN). Prior quarter = gray `#c7c7cc`, current = blue `#0071e3`.

---

## 4. Data pipeline — fully automated (as of 2026-07-01)

Every number in this file is **auto-synced from the review Markdown files** by the crawler. No more
manual re-extract; there is no data drift because sync and validation share one computation.

- **Source of truth:** `Yuanta_App_Reviews.md` / `SinoPac_App_Reviews.md` / `Cathay_App_Reviews.md`
  (the scraped review tables at the project root).
- **Weekly job:** macOS LaunchAgent `com.yuanta.review-crawler-agent` runs **Mondays 09:00 Taipei**
  (`scraper_agent.py --run-now --deploy`): scrape Google Play + App Store → update the 3 `.md` →
  **sync this HTML → validate → deploy** (`deploy.sh` → `yuanta-app-reviews-2.pages.dev`).
- **`review-crawler-agent/web_data.py`** — parses the 3 `.md` and computes every dashboard number.
  Shared by sync **and** validate, so they can never diverge.
- **`review-crawler-agent/web_sync.py`** — injects the numbers into this file in place: `allReviews`
  JSON, the 3 Chart.js datasets, headline KPIs, hero brand cards, 核心指標 cards, 月度趨勢,
  競品雙平台快覽, Tab-2 summaries, trend-insight prose deltas/avgs, 6 月低分 counts, modal-title delta.
  Fail-loud: each `_subn` asserts its anchor still matches (raises if the markup moved).
- **`review-crawler-agent/validate_dashboard.py`** — re-checks the injected numbers against
  `web_data`; the weekly deploy aborts if anything is off.
- **Coverage:** 87 structured numbers, all data-derived. `reviewDatabase` curated **sample reviews**
  remain hand-picked (they illustrate a point, not aggregate).

**Still hand-authored (qualitative, not computable from star ratings):** pain-point topic %s,
高頻議題標籤 counts, version labels, market-share %, curated modal reviews, and the **directional
verbs** in the insight prose (拉升至 / 回落至 / 僅 / 急跌 — the *numbers* auto-update, but if a
trend reverses the *wording* needs a human).

> **⚠️ Editing gotcha:** don't hand-edit a synced number — `web_sync.py` overwrites it next run.
> Structural/markup changes are fine, but if you rename a class or reword a **synced** sentence,
> update the matching anchor regex in `web_sync.py` (its `_subn` will fail loudly if an anchor breaks).
> After any data-shape change, run `web_sync.py` then `validate_dashboard.py` locally to confirm green.

---

## 5. Non-obvious decisions & gotchas (READ before editing)

These caused real bugs during the build. Don't reintroduce them.

1. **`.mt` is the monthly-trend BAR**, not a tag. It's `height:11px; overflow:hidden`. Reusing the
   class anywhere else (the modal tag did this) inherits that height and **clips the content**.
   The modal tag is therefore `.mtag`. → Grep for class collisions before naming new classes.
2. **`.item+.item{margin-top:10px}` is scoped to `.pcard`.** It's only for vertically-stacked items
   inside pain/deep cards. Unscoped, it leaked into the 3-up grids and broke equal card heights.
3. **Modal scroll requires `.mb{min-height:0}` + `.mh{flex-shrink:0}`.** Without `min-height:0`,
   the flex column overflows `max-height` and (being centered) clips the header. Classic flexbox trap.
4. **Cards are borderless.** White cards float on the gray page via `--elev` shadow; nested panels
   separate by gray fill (`--panel`). No `1px` strokes, no colored top-accents, no `.sec-bar` lines —
   these all read as "AI-generated." Keep it that way.
5. **The `.src` hover hint ("點擊查看評論來源") is in normal flow** (`margin-top:auto`), not absolute.
   Absolute positioning made it overlap the paragraph text on short cards.
6. **CJK in small pills needs ≥5px vertical padding + line-height ≥1.4**, or glyph tops clip.
7. **國泰 green is text-based in the modal:** `showReviewSource()` greens the tag when
   `data.tag` includes `國泰`, independent of the stored `tagClass`. Severity reds (`tgr` on
   系統當機/報價連線/耗電過熱) intentionally stay red — they encode severity, not brand.
8. **Anti-AI-tell pass (impeccable-design-polish):** removed purple→violet gradients, the hero purple
   glow, `#635bff` accents, and uppercase wide-tracked section labels. Single blue accent throughout.

### Tooling note
- Previewing via the gstack `browse` binary: screenshots only write to `/tmp` or the workspace, and
  `file://` reads outside the workspace are blocked — copy the HTML to `/tmp` first.
- Phosphor's unpkg loader sometimes logs `ERR_SSL_BAD_RECORD_MAC_ALERT` for the **Fill** weight,
  which we don't use. Harmless. (Self-hosting would remove it — see §6.)

---

## 6. Known limitations & next steps

Ordered by value.

1. **Accessibility pass (highest value).** No verified WCAG AA contrast audit. The modal lacks a
   focus-trap, `role="dialog"`, `aria-modal`, and focus return on close. Add these.
2. **Tab 3 「專家聯席戰略分析」 is a locked placeholder.** The original content is password-gated /
   encrypted and was not ported. Decide whether to author real content or remove the tab.
3. **Self-host Chart.js + Phosphor** instead of CDN, for offline use and to kill the SSL noise.
4. **File size ~410 KB** (inlined ~1,257-review JSON, grows each weekly crawl). The review table
   renders all filtered rows; fine at current volume, but virtualize if the dataset grows much larger.
5. ~~**No live data.**~~ **RESOLVED (2026-07-01)** — reviews now auto-refresh + redeploy weekly via
   the crawler (§4). Remaining caveat: the insight-prose *wording* (direction verbs) is static even
   though its numbers sync — revisit if a brand's quarter-over-quarter trend flips direction.

---

## 7. Changelog

- **2026-07-01** — **Full-page data sync.** Every structured number (headline KPIs, hero brand cards,
  核心指標, 月度趨勢, 競品雙平台快覽, Tab-2 summaries, trend-insight prose, 6 月低分 counts, modal
  delta) is now auto-injected from the `.md` data; independent audit passes **87/87**. Added
  `web_data.py` + `web_sync.py`; rewrote `validate_dashboard.py` to check this file. The crawler now
  scrapes → syncs → validates → **deploys this file** weekly. Data refreshed to **1,257**
  (元大 413 · 永豐 405 · 國泰 439).
- **2026-07-01** — **Promoted to source of truth.** Renamed `Yuanta_Reviews_Dashboard_B2.html` →
  `Yuanta_Reviews_Web.html`; archived the old `index.html` + `Yuanta_Reviews_Dashboard.html` under
  `archive/` (excluded from deploy); added `_redirects` so `/` serves this file on Cloudflare Pages.
- **2026-06-30** — 國泰 brand tags switched to Cathay green (`.tgc`/`.pc`); modal tag greens for 國泰
  via text rule. Score card / competitor card / severity reds unchanged.
- **2026-06-29** — Modal redesign: fixed header clipping (flexbox `min-height:0`), fixed the `.mt`
  class collision (→ `.mtag`), in-flow hover hint, equal card heights in 競品比較洞察, iOS-sheet styling.
- **2026-06-29** — Applied Phosphor icon system (replaced all UI emoji); removed all card strokes /
  section accent lines (borderless model).
- **2026-06-26** — Apple design-system polish (tokens, single blue accent, lighter weights,
  anti-AI-tell pass). Initial B2 build: full rebuild with extracted data, 3 tabs, charts, modal.
