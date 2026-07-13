# Reviews 2.0 — scikit-learn 分析管線

把 `review-crawler-agent` 抓回來的三家券商 App 評論（元大 / 國泰 / 永豐大戶）
轉成一個**競品分析儀表板**。全程資料驅動、可重跑：資料一更新，重跑即可刷新整站。

## 它做什麼

| 階段 | 模組 | 技術 |
|---|---|---|
| 解析 | `parse_reviews.py` | 把 `*_App_Reviews.md` 表格 → 結構化 DataFrame（1,212 則） |
| 斷詞 | `text_zh.py` | `jieba` + 金融自訂詞庫（停損單／複委託／零股…），過濾停用詞 |
| 主題 | `themes.py` | `TfidfVectorizer` → `NMF`，**三家合併語料**抽 8 個主題（同一座標可比） |
| 意圖 | `intent.py` | 弱監督種子（星等＋詞典）→ `LogisticRegression`；低信心歸「其他」 |
| 彙整 | `analyze.py` | 各家 KPI／星等分布／月趨勢／版本／主題占比／**競品落差** → `site/data.json` |
| 出站 | `build_site.py` | Jinja2 + Chart.js 渲染 → `site/index.html`（資料內嵌，可直接開檔） |

## 怎麼跑

```bash
# 用工作區根目錄那顆已裝好套件的 venv
PY="../../.venv-ioscrawl311/bin/python3"      # 或自建：python -m venv .venv && pip install -r requirements.txt

cd analysis
$PY build_site.py --fresh      # 重新分析並產生 ../site/index.html + data.json
```

單獨除錯任一階段：

```bash
$PY parse_reviews.py   # 看解析統計
$PY themes.py          # 看 8 個主題與關鍵詞
$PY intent.py          # 看意圖分類 + 5-fold F1
$PY analyze.py         # 只重算 data.json
```

## 輸出

- `../site/index.html` — 自帶資料的單頁儀表板（中文，深色）。
- `../site/data.json` — 純資料層，可餵給其他前端／報表。

## 部署（Cloudflare Pages）

新舊兩站已**完全分開**，各自獨立的 Pages 專案／網址，互不影響：

| 站別 | 內容 | 專案 / 網址 | 部署指令 |
|---|---|---|---|
| 舊版 | 根目錄手作儀表板 | `yuanta-app-reviews-2` → yuanta-app-reviews-2.pages.dev | `../deploy.sh`（已排除 `site/`、`analysis/`） |
| 新版 | 本管線輸出 `site/` | `yuanta-app-reviews-ml` → yuanta-app-reviews-ml.pages.dev | `../deploy-site.sh` |

部署新站（先重建再推）：

```bash
../../.venv-ioscrawl311/bin/python3 build_site.py --fresh   # 重建 site/
cd .. && ./deploy-site.sh                                    # 部署到 yuanta-app-reviews-ml
```

## 模型備註

- 主題與意圖皆**無人工標註**：主題用 NMF 非監督抽取，意圖用弱監督 bootstrap。
  指標（種子數、`F1_macro`）會印在 `intent.py` 輸出與頁尾，方便稽核。
- 中文斷詞品質決定主題品質；要調主題，先擴充 `userdict_zh.txt` / `stopwords_zh.txt`，
  或在 `themes.py` 調 `N_THEMES` 與 `_LABEL_RULES`。
