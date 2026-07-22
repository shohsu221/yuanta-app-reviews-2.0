# 專案架構重構與優化待辦清單 (TODO)

## 問題與優化建議 (依嚴重性排序)

### 🔴 高嚴重性 (High Severity)
1. **專案結構混亂、方法關係不明確（已完成）**：專案主方法（`review-crawler-agent/`）與舊版方法（`analysis/`、`site/`）檔案散落在根目錄，使整體結構難以維護。已依下表進行檔案歸類與遷移，同時將 `review-crawler-agent/` 改名為 `crawler/`、`analysis/` 更名為 `experiments/` 以凸顯其試驗性質；主方法依賴統一放在根目錄的 `requirements.txt`，試驗依賴則留在各試驗資料夾中（如 `experiments/requirements.txt`），保持根目錄乾淨：

| 根目錄原檔案/資料夾 | 建議重構去處 | 理由 |
| :--- | :--- | :--- |
| `lead-applied-scientist-persona.md` | **`.agents/`** | 屬於 AI 代理人角色人設，應放進 AI 專區。 |
| `lead_marketing_strategist_agent_skill.md` | **`.agents/skills/`** | 屬於 AI 代理人技能說明，應放進 AI 專區。 |
| `tailwind.config.js`<br>`tailwind.input.css` | **`.archive/`** (或刪除) | 主站已改用原生 Apple CSS，不再使用 Tailwind。這兩份為舊檔案，應歸檔或刪除。 |
| `assets/` (資料夾) | **`.archive/`** (或刪除) | 僅舊版網頁引用其樣式與 JS，新版網頁無引用，應歸檔或刪除。 |
| `deploy.sh` | **`deploy/`** | 主方法（手作儀表板）的運維部署指令，應移出根目錄。 |
| `deploy-site.sh` | **`experiments/`** | 試驗方法（ML版網頁）的部署指令，應隨試驗模組封裝。 |
| `*_App_Reviews.md` | **`data/raw/`** (建議改 JSON) | 原始爬取數據，屬於資料層，應統一管理。 |
| `Yuanta_Reviews_Comparison_Q1_vs_Q2_2026.md`<br>`three_expert_analysis_report.md`<br>`UXR.md`<br>`ROLLBACK.md`<br>`DEVLOG.md` | **`docs/`** | 屬於專案文檔、分析報告與歷史日誌，應移入文檔庫。 |
| `review-crawler-agent/` (資料夾) | 重新命名為 **`crawler/`** | 簡化主方法爬蟲模組的名稱。 |
| `analysis/` (資料夾) | 重新命名為 **`experiments/`** | 凸顯其試驗性質，與主線區隔。 |
| `site/` (資料夾) | 加入 **`.gitignore`** 排除 | ML 的靜態建置產物不應提交進 Git，應在 CI/CD 中動態編譯。 |
| `archive/` (資料夾) | 重新命名為 **`.archive/`** | 加點隱藏以減少根目錄視覺干擾。 |
| `Yuanta_Reviews_Web.html` | 移入 **`web/`** 並拆分為 `index.html` / `static/` | 轉為靜態網頁架構，CSS/JS 獨立管理，並由 JS 異步載入數據。 |
| `_redirects` | 移入 **`web/`** | 隨網頁入口一起打包，便於 Cloudflare Pages 發布。 |

2. **數據儲存與傳輸使用 Markdown 格式不穩定（已完成）**：目前爬蟲將原始評論儲存為 `*_App_Reviews.md` 內的 Markdown 表格，解析時極易因為用戶評論中的換行、管道符號（`|`）或 Markdown 特殊字元導致解析破裂。建議改為使用標準的 JSON 檔案儲存原始數據，並更新後續的同步與分析程式。
3. **資料至網頁端之流程問題**：從原始資料庫到前端網頁的整體自動化銜接流程尚不完善。具體問題包括：(1) LLM 整理產出的 Markdown 分析摘要缺乏簡單流暢的管道自動匯入至 Web 端展示；(2) 哪些數據可用 Python 腳本（如 `web_sync.py`）直接快速自動更新、哪些位置屬LLM編輯不明確；(3) 網頁中部分文字與數據（如精選評論、特定洞察段落）仍屬靜態硬編碼，不會隨著 `data/` 最新資料庫的爬取更新而自動同步統計數字與改變。
4. **儀表板季度邏輯硬編碼，Q3 起資料將消失**：`web_data.py` 中季度篩選寫死 `Q1 = 月1-3, Q2 = 月4-6`，`web_sync.py` 的月度趨勢也固定只處理 4/5/6 月，`static_summary.py`（1060 行）同樣大量硬編碼季度 HTML 模板。進入 Q3（7月）後，新爬取的評論將完全不會出現在儀表板統計與圖表中。建議：(1) 將季度範圍改為由設定檔或自動偵測當前日期動態決定；(2) 讓月度趨勢自動擴展到實際有資料的月份；(3) 拆分 `static_summary.py` 中的模板與邏輯，降低維護成本。

### 🟡 中嚴重性 (Medium Severity)
5. **架構問題**：`Yuanta_Reviews_Web.html` 內置大量 JSON 數據，且以正則表達式更新，導致網頁本體過於龐大（每次資料更新都會破壞網頁快取，浪費傳輸頻寬）。建議：(1) 新增 `web/` 資料夾，將網頁重構為 HTML + CSS + JS 獨立管理的標準靜態架構；(2) 前端透過瀏覽器端 `fetch` 異步載入結構化的 `data.json`，實現網頁與數據解耦，提升瀏覽器快取效能，並免除脆弱的正則替換。
6. **自動化部署跨平台支援不佳**：目前的部署腳本為 Linux/macOS 專用且包含 macOS 硬編碼的臨時路徑（/private/tmp/），導致 Windows 系統無法原生執行與測試。建議將臨時路徑改為專案內部的相對路徑，並移交至 GitHub Actions 進行雲端自動化部署（引入 CI/CD）。
7. **建立檔案儲存機制**：目前爬蟲每次執行均整個重寫單一 `*_App_Reviews.md`，隨評論累積檔案將持續膨脹，單個檔案可能過大；此外LLM 整理的分析報告（如 `Yuanta_Reviews_Comparison_Q1_vs_Q2_2026.md`）可能為AI產出，更新後會被覆蓋。建議採用「時間分片 + 摘要獨立歸檔」策略：(1) 原始評論依月份切分為獨立 JSON 檔（`data/raw/{app}/YYYY-MM.json`），滿月封存不再修改，爬蟲只寫當月檔案，去重速率不受歷史累積量影響；(2) 每次 AI 整理完成後，自動輸出帶時間戳的摘要檔至 `data/summaries/{app}/YYYY-MM-DD_summary.md`，永不覆蓋舊摘要；(3) 維護 `data/summaries/{app}/index.json` 作為摘要索引，供前端異步載入。

### 🟢 低嚴重性 (Low Severity)
8. **Git 忽略設定不完全**：未排除根目錄的本機虛擬環境資料夾（.venv/）與編譯產物。建議調整 .gitignore 設定，避免本機暫存變更污染 Git 歷史紀錄。
9. **缺乏專案說明文件**：原始專案根目錄下沒有 README.md，新進協作者難以快速上手。建議新增一份 README.md，說明專案目的、目錄結構、兩套方法的工作流程、依賴安裝與部署方式。
10. **爬蟲缺乏錯誤重試與速率控制**：`gplay_scraper.py` 和 `appstore_scraper.py` 在網路請求失敗時直接回傳空列表，沒有任何重試機制。App Store 爬取還依賴從 HTML 水合中提取的臨時 Bearer token，來源脆弱。一次網路波動即導致整個平台本週資料為零。建議：(1) 為所有 HTTP 請求加入指數退避重試（如 `tenacity` 或 `urllib3.util.retry`）；(2) 加入請求間的隨機延遲（rate limiting），降低被平台封鎖的風險；(3) 在 App Store token 失效時自動重新取得。

---

## 重構後的專案樹狀圖 (Proposed Directory Tree)

```text
輿論平台/ (重構後)
├── 📁 .github/                       # GitHub Actions 自動化部署 CI/CD
│   └── 📁 workflows/
│       └── deploy.yml                # 雲端建置與部署腳本
│
├── 📁 .agents/                       # AI 協作代理人專區
│   ├── 📄 AGENTS.md                  # AI 協作規則定義
│   ├── 📄 lead-applied-scientist-persona.md          # 代理人人設
│   └── 📁 skills/
│       └── lead_marketing_strategist_agent_skill.md  # 代理人技能
│
├── 📁 .archive/                      # 舊版與已停用程式碼封存區
│   ├── 📄 Yuanta_Reviews_Dashboard.html
│   ├── 📄 tailwind.config.js
│   └── 📄 tailwind.input.css
│
├── 📁 data/                          # 數據統一管理目錄(給電腦傳輸用)
│   ├── 📁 comments/                  # 原始評論（按季度）
│   └── 📁 summaries/                 # AI 整理摘要歸檔（帶時間戳，永不覆蓋）
│       ├── 📄 2026-Q1_summary.md         # 季度整季摘要
│       ├── 📄 2026-07-08_summary.md      # 每次執行後自動產出
│       ├── 📄 2026-07-15_summary.md
│       └── 📄 index.json                 # 摘要索引，供前端異步載入

│
├── 📁 deploy/                        # 【主方法】部署與運維指令目錄
│   └── 📄 deploy.sh
│
├── 📁 docs/                          # 專案文檔與研究報告(給人看的)
│   ├── 📄 three_expert_analysis_report.md
│   ├── 📄 UXR.md
│   ├── 📄 ROLLBACK.md
│   └── 📄 DEVLOG.md
│
├── 📁 crawler/                       # 【主方法】爬蟲與自動更新模組
│
├── 📁 experiments/                   # 【試驗方法】機器學習分析管線
│   ├── 📄 requirements.txt           # 機器學習與 NLP 的專屬依賴 (不污染根目錄)
│   └── 📄 deploy-site.sh             # 試驗網頁部署腳本 (隨試驗區封裝)
│
├── 📁 functions/                     # Cloudflare Pages 雲端函數 (平台要求保留於根目錄)
│   └── 📁 api/
│       └── 📄 expert.js              # 專家分析密碼驗證與數據傳輸 API
│
├── 📁 web/                           # 【主方法】前端網頁與靜態資源模組
│   ├── 📄 index.html                 # 儀表板首頁入口 (由 JS 異步 fetch 資料)
│   ├── 📄 data.json                  # (由爬蟲生成/不進 Git) 儀表板結構化數據
│   ├── 📄 _redirects                 # Cloudflare Pages 重導向規則
│   └── 📁 static/                    # 靜態資源目錄
│       ├── 📁 css/
│       │   └── 📄 main.css           # 獨立樣式表
│       └── 📁 js/
│           ├── 📄 dashboard.js       # 頁面交互邏輯
│           └── 📄 charts.js          # 圖表配置與資料載入
│
├── 📄 .gitignore                     # 排除 .venv/、site/ 與 web/data.json
├── 📄 requirements.txt               # 主方法依賴 (僅保留爬蟲核心)
├── 📄 README.md                      # 專案說明文件
└── 📄 TODO.md                        # 本重構任務清單
```
