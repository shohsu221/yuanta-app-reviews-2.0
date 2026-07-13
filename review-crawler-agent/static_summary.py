"""
static_summary.py — 將 Markdown 最新統計同步到靜態首頁摘要
"""
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)


@dataclass
class AppSummary:
    key: str
    label: str
    path: Path
    total: int
    updated_at: datetime
    latest_review_date: datetime
    rows: list[tuple[datetime, str, int, str]]
    detail_rows: list[dict]


_UPDATED_RE = re.compile(r"最後更新時間\*\*：(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")
_TOTAL_RE = re.compile(r"資料累計總量\*\*：雙平台共\s*(\d+)\s*則")
_ROW_DATE_RE = re.compile(r"^\|\s*\d+\s*\|\s*(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}\s*\|", re.MULTILINE)


def _read_summary(key: str, label: str, filename: str) -> AppSummary:
    path = Path(config.BASE_DIR) / filename
    content = path.read_text(encoding="utf-8")

    updated_match = _UPDATED_RE.search(content)
    total_match = _TOTAL_RE.search(content)
    rows = _parse_review_rows(content)
    detail_rows = _parse_detail_review_rows(content)
    row_dates = [row[0].strftime("%Y-%m-%d") for row in rows]

    if not updated_match or not total_match or not row_dates:
        raise ValueError(f"{filename} 缺少更新時間、總量或評論列日期")

    updated_at = datetime.strptime(updated_match.group(1), "%Y-%m-%d %H:%M")
    latest_review_date = max(datetime.strptime(d, "%Y-%m-%d") for d in row_dates)

    return AppSummary(
        key=key,
        label=label,
        path=path,
        total=int(total_match.group(1)),
        updated_at=updated_at,
        latest_review_date=latest_review_date,
        rows=rows,
        detail_rows=detail_rows,
    )


def _parse_review_rows(content: str) -> list[tuple[datetime, str, int, str]]:
    rows = []
    for line in content.splitlines():
        if not re.match(r"^\|\s*\d+\s*\|", line):
            continue
        parts = line.split("|")
        if len(parts) < 8:
            continue
        try:
            row_date = datetime.strptime(parts[2].strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        platform = parts[3].strip()
        rating_match = re.search(r"\((\d)\)", parts[5])
        if not rating_match:
            continue
        review_text = parts[7].strip() if len(parts) > 7 else ""
        rows.append((row_date, platform, int(rating_match.group(1)), review_text))
    return rows


def _parse_detail_review_rows(content: str) -> list[dict]:
    rows = []
    for line in content.splitlines():
        if not re.match(r"^\|\s*\d+\s*\|", line):
            continue
        parts = line.split("|")
        if len(parts) < 8:
            continue
        try:
            row_date = datetime.strptime(parts[2].strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        rating_match = re.search(r"\((\d)\)", parts[5])
        if not rating_match:
            continue
        rows.append({
            "date": row_date,
            "platform": parts[3].strip(),
            "username": parts[4].strip(),
            "rating": int(rating_match.group(1)),
            "version": parts[6].strip(),
            "review_text": parts[7].strip(),
        })
    return rows


def _quarter_rows(summary: AppSummary, quarter: str) -> list[tuple[datetime, str, int, str]]:
    if quarter == "q1":
        return [row for row in summary.rows if 1 <= row[0].month <= 3]
    if quarter == "q2":
        return [row for row in summary.rows if 4 <= row[0].month <= 6]
    raise ValueError(f"Unknown quarter: {quarter}")


def _avg(rows: list[tuple[datetime, str, int, str]], platform: Optional[str] = None) -> float:
    filtered = [row for row in rows if platform is None or row[1] == platform]
    if not filtered:
        return 0.0
    return sum(row[2] for row in filtered) / len(filtered)


def _count(rows: list[tuple[datetime, str, int, str]], platform: Optional[str] = None) -> int:
    return len([row for row in rows if platform is None or row[1] == platform])


def _dist_5_to_1(rows: list[tuple[datetime, str, int, str]]) -> list[int]:
    return [sum(1 for row in rows if row[2] == rating) for rating in range(5, 0, -1)]


def _fmt(value: float) -> str:
    return f"{value:.2f}"


def _delta(q1: float, q2: float) -> str:
    diff = q2 - q1
    arrow = "↑" if diff >= 0 else "↓"
    return f"{arrow} {diff:+.2f} ★"


def _replace_once(content: str, pattern: str, replacement: str) -> str:
    return re.sub(pattern, replacement, content, count=1, flags=re.DOTALL)


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _issue_tags(rows: list[tuple[datetime, str, int, str]], limit: int = 5) -> list[tuple[str, int]]:
    issue_keywords = [
        ("系統/當機", ["當機", "閃退", "打不開", "無法開", "崩潰", "空白"]),
        ("登入/連線", ["登入", "連線", "伺服器", "轉圈", "卡住", "忙碌"]),
        ("下單/交易", ["下單", "交易", "停損", "沖銷", "期貨", "選擇權"]),
        ("介面/字體", ["介面", "字體", "太小", "看不見", "畫面", "按鈕"]),
        ("開戶/審核", ["開戶", "審核", "上傳", "申請", "資料"]),
        ("耗電/過熱", ["耗電", "發燙", "過熱", "很燙", "電量"]),
        ("K線/圖表", ["K線", "線圖", "圖表", "均線", "報價"]),
        ("客服/回覆", ["客服", "回覆", "沒人接", "聯絡", "留言"]),
    ]
    counts = []
    for label, keywords in issue_keywords:
        count = sum(1 for row in rows if any(keyword in row[3] for keyword in keywords))
        if count:
            counts.append((label, count))
    counts.sort(key=lambda item: item[1], reverse=True)
    return counts[:limit]


def _monthly_stats(rows: list[tuple[datetime, str, int, str]]) -> list[dict]:
    stats = []
    for month in [1, 2, 3, 4, 5, 6]:
        month_rows = [row for row in rows if row[0].month == month]
        if not month_rows:
            continue
        stats.append({
            "label": f"{month}月",
            "count": len(month_rows),
            "avg": _avg(month_rows),
            "one_star": sum(1 for row in month_rows if row[2] == 1),
        })
    return stats


def _brand_style(key: str) -> dict:
    styles = {
        "yuanta": {
            "tag": "tag-blue",
            "text": "text-blue-300",
            "bar": "linear-gradient(90deg,#635bff 0%,#f96bee 100%)",
        },
        "sinopac": {
            "tag": "tag-amber",
            "text": "text-amber-300",
            "bar": "linear-gradient(90deg,#a78bfa 0%,#ff80c8 100%)",
        },
        "cathay": {
            "tag": "tag-rose",
            "text": "text-rose-300",
            "bar": "linear-gradient(90deg,#c4b5fd 0%,#f96bee 58%,#ff80c8 100%)",
        },
    }
    return styles[key]


def _detail_app_name(summary: AppSummary) -> str:
    names = {
        "yuanta": "元大投資先生",
        "sinopac": "永豐大戶投",
        "cathay": "國泰證券",
    }
    return names[summary.key]


def _rating_color(rating: int) -> str:
    if rating <= 2:
        return "#ea2261"
    if rating == 3:
        return "#f5a524"
    return "#15be53"


def _display_review_text(text: str) -> str:
    text = re.sub(r"\*\*【(.+?)】\*\*", r"【\1】", text)
    return re.sub(r"\s+", " ", text).strip()


def _detail_table_rows(summary: AppSummary) -> str:
    rows = []
    for row in sorted(summary.detail_rows, key=lambda item: item["date"], reverse=True):
        stars = "★" * row["rating"] + "☆" * (5 - row["rating"])
        rows.append(f"""
                                <tr class="border-t" style="border-color:#e5edf5;">
                                    <td class="px-3 py-3 align-top text-[11px] text-gray-500 whitespace-nowrap">{row['date'].strftime('%Y-%m-%d %H:%M')}</td>
                                    <td class="px-3 py-3 align-top text-[11px] text-gray-500 whitespace-nowrap">{_html_escape(row['platform'])}</td>
                                    <td class="px-3 py-3 align-top text-[11px] text-gray-500 whitespace-nowrap">{_html_escape(row['version'])}</td>
                                    <td class="px-3 py-3 align-top text-xs font-semibold whitespace-nowrap" style="color:#273951;">{_html_escape(row['username'])}</td>
                                    <td class="px-3 py-3 align-top text-xs font-bold whitespace-nowrap" style="color:{_rating_color(row['rating'])};">{stars}</td>
                                    <td class="px-3 py-3 align-top text-xs leading-relaxed" style="color:#273951;min-width:24rem;">{_html_escape(_display_review_text(row['review_text']))}</td>
                                </tr>""")
    return "\n".join(rows)


def _detail_reviews_html(summaries: list[AppSummary]) -> str:
    total = sum(summary.total for summary in summaries)
    latest_update = max(summary.updated_at for summary in summaries).strftime("%Y-%m-%d")

    cards = []
    sections = []
    for summary in summaries:
        style = _brand_style(summary.key)
        rows = summary.detail_rows
        gp_count = sum(1 for row in rows if row["platform"] == "Google Play")
        appstore_count = sum(1 for row in rows if row["platform"] == "App Store")
        low_count = sum(1 for row in rows if row["rating"] <= 2)
        avg = sum(row["rating"] for row in rows) / len(rows) if rows else 0
        low_pct = low_count / len(rows) * 100 if rows else 0
        app_name = _detail_app_name(summary)

        cards.append(f"""
                <div class="rounded-xl border border-white/10 bg-white/[0.025] p-4">
                    <div class="flex items-center justify-between gap-3">
                        <span class="text-xs {style['tag']} px-2.5 py-0.5 rounded-full font-semibold">{app_name}</span>
                        <span class="text-xs text-gray-500">{summary.total} 則</span>
                    </div>
                    <div class="mt-3 flex items-end justify-between gap-3">
                        <div>
                            <div class="text-3xl font-extrabold text-white">{_fmt(avg)}</div>
                            <div class="text-[11px] text-gray-500">平均評分</div>
                        </div>
                        <div class="text-right text-[11px] text-gray-500 leading-relaxed">
                            <div>Google Play {gp_count}</div>
                            <div>App Store {appstore_count}</div>
                        </div>
                    </div>
                    <div class="mt-3 h-2 rounded-full overflow-hidden" style="background:#e5edf5;">
                        <div class="h-full rounded-full" style="width:{max(4, low_pct):.1f}%;background:{style['bar']};"></div>
                    </div>
                    <div class="mt-2 text-[11px] text-gray-500">1-2★ 低分評論 {low_count} 則</div>
                </div>""")

        sections.append(f"""
            <section class="glass-card rounded-2xl p-5 md:p-6 border border-white/10">
                <div class="flex flex-col md:flex-row md:items-end md:justify-between gap-3 mb-4">
                    <div>
                        <span class="text-xs {style['tag']} px-2.5 py-1 rounded-full font-bold">{app_name}</span>
                        <h3 class="text-xl font-extrabold text-white mt-2">{app_name} 詳細評論</h3>
                        <p class="text-xs text-gray-500 mt-1">共 {summary.total} 則，依評論時間由新到舊排列。</p>
                    </div>
                    <div class="text-xs text-gray-500">資料來源：Google Play / App Store 公開評論</div>
                </div>
                <div class="rounded-xl border overflow-auto" style="border-color:#e5edf5;max-height:34rem;background:#ffffff;">
                    <table class="min-w-full text-left border-collapse">
                        <thead class="sticky top-0 z-10" style="background:#f6f9fc;color:#64748d;">
                            <tr>
                                <th class="px-3 py-2 text-[11px] font-bold whitespace-nowrap">時間</th>
                                <th class="px-3 py-2 text-[11px] font-bold whitespace-nowrap">平台</th>
                                <th class="px-3 py-2 text-[11px] font-bold whitespace-nowrap">版本</th>
                                <th class="px-3 py-2 text-[11px] font-bold whitespace-nowrap">用戶</th>
                                <th class="px-3 py-2 text-[11px] font-bold whitespace-nowrap">評分</th>
                                <th class="px-3 py-2 text-[11px] font-bold">評論內容</th>
                            </tr>
                        </thead>
                        <tbody>
{_detail_table_rows(summary)}
                        </tbody>
                    </table>
                </div>
            </section>""")

    return f"""
    <!-- ═══════════════ DETAILED USER REVIEWS PANEL ═══════════════ -->
    <div id="content-reviews" class="space-y-8 hidden scroll-fade">
        <section class="glass-card rounded-2xl p-5 md:p-6 border border-white/10">
            <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5">
                <div class="max-w-3xl">
                    <div class="flex flex-wrap items-center gap-2 mb-3">
                        <span class="text-xs tag-purple px-2.5 py-1 rounded-full font-bold">詳細用戶評論</span>
                        <span class="text-xs text-gray-500">更新 {latest_update} · 三家共 {total} 則</span>
                    </div>
                    <h2 class="text-xl md:text-2xl font-extrabold text-white tracking-tight">三大券商完整公開評論清單</h2>
                    <p class="text-sm text-gray-400 mt-2 leading-relaxed">收錄元大投資先生、永豐大戶投、國泰證券於 Google Play 與 App Store 的公開評論，保留日期、平台、版本、用戶、評分與原始評論內容。</p>
                </div>
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-5">
{''.join(cards)}
            </div>
        </section>
{''.join(sections)}
    </div>"""


def _replace_detail_reviews(content: str, summaries: list[AppSummary]) -> str:
    block = _detail_reviews_html(summaries)
    pattern = (
        r"\s*<!-- ═══════════════ DETAILED USER REVIEWS PANEL ═══════════════ -->"
        r".*?(?=\n\s*<!-- ═══════════════ EXPERT STRATEGIC ANALYSIS PANEL ═══════════════ -->)"
    )
    return re.sub(pattern, "\n" + block, content, count=1, flags=re.DOTALL)


def _replace_stripe_chart_colors(content: str) -> str:
    """Keep generated Chart.js bars aligned with the Stripe-inspired palette."""
    replacements = [
        ("rgba(83,58,253,0.72)", "rgba(99,91,255,0.72)"),
        ("rgba(0,212,255,0.68)", "rgba(249,107,238,0.68)"),
        ("rgba(234,34,97,0.68)", "rgba(249,107,238,0.68)"),
        ("rgba(83,58,253,0.42)", "rgba(99,91,255,0.42)"),
        ("rgba(0,212,255,0.38)", "rgba(196,181,253,0.40)"),
        ("rgba(249,107,238,0.38)", "rgba(196,181,253,0.40)"),
        ("rgba(234,34,97,0.38)", "rgba(255,128,200,0.40)"),
        ("rgba(83,58,253,0.82)", "rgba(99,91,255,0.82)"),
        ("rgba(83,58,253,0.86)", "rgba(99,91,255,0.86)"),
        ("rgba(0,212,255,0.72)", "rgba(196,181,253,0.72)"),
        ("rgba(249,107,238,0.72)", "rgba(249,107,238,0.72)"),
        ("rgba(234,34,97,0.72)", "rgba(255,128,200,0.72)"),
        ("#533afd", "#635bff"),
        ("#00d4ff", "#f96bee"),
    ]
    for before, after in replacements:
        content = content.replace(before, after)
    content = content.replace("borderColor: '#ea2261'", "borderColor: '#f96bee'")
    content = content.replace(
        "borderColor: ['#635bff', '#00d4ff', '#ea2261']",
        "borderColor: ['#635bff', '#c4b5fd', '#f96bee']",
    )
    content = content.replace(
        "borderColor: ['#635bff', '#f96bee', '#ea2261']",
        "borderColor: ['#635bff', '#c4b5fd', '#f96bee']",
    )
    content = content.replace(
        "backgroundColor: ['rgba(99,91,255,0.82)', 'rgba(249,107,238,0.72)', 'rgba(255,89,150,0.72)']",
        "backgroundColor: ['rgba(99,91,255,0.82)', 'rgba(196,181,253,0.72)', 'rgba(255,128,200,0.72)']",
    )
    content = content.replace(
        "backgroundColor: ['rgba(99,91,255,0.42)', 'rgba(196,181,253,0.40)', 'rgba(255,89,150,0.38)']",
        "backgroundColor: ['rgba(59,130,246,0.42)', 'rgba(245,158,11,0.42)', 'rgba(244,63,94,0.40)']",
    )
    content = content.replace(
        "backgroundColor: ['rgba(99,91,255,0.82)', 'rgba(196,181,253,0.72)', 'rgba(255,128,200,0.72)']",
        "backgroundColor: ['rgba(59,130,246,0.82)', 'rgba(245,158,11,0.78)', 'rgba(244,63,94,0.76)']",
    )
    content = content.replace(
        "borderColor: ['#635bff', '#c4b5fd', '#f96bee']",
        "borderColor: ['#3b82f6', '#f59e0b', '#f43f5e']",
    )
    return content


def _compact_summary_html(summaries: list[AppSummary]) -> str:
    by_key = {summary.key: summary for summary in summaries}
    total = sum(summary.total for summary in summaries)
    latest_update = max(summary.updated_at for summary in summaries).strftime("%Y-%m-%d")
    latest_review = max(summary.latest_review_date for summary in summaries).strftime("%Y/%m/%d")

    brand_cards = []
    issue_cloud = []
    q2_rows_all = []
    for summary in summaries:
        q1 = _quarter_rows(summary, "q1")
        q2 = _quarter_rows(summary, "q2")
        q2_rows_all.extend(q2)
        delta = _avg(q2) - _avg(q1)
        delta_class = "text-green-300" if delta >= 0 else "text-rose-300"
        delta_label = f"{delta:+.2f}"
        style = _brand_style(summary.key)
        one_star_pct = (sum(1 for row in q2 if row[2] == 1) / len(q2) * 100) if q2 else 0
        brand_cards.append(f"""
                <div class="rounded-xl border border-white/10 bg-white/[0.025] p-4">
                    <div class="flex items-center justify-between gap-3">
                        <span class="text-xs {style['tag']} px-2.5 py-0.5 rounded-full font-semibold">{summary.label}</span>
                        <span class="text-xs {delta_class} font-bold">Q2 {delta_label} ★</span>
                    </div>
                    <div class="mt-3 flex items-end justify-between gap-3">
                        <div>
                            <div class="text-3xl font-extrabold text-white">{_fmt(_avg(q2))}</div>
                            <div class="text-[11px] text-gray-500">Q2 平均評分</div>
                        </div>
                        <div class="text-right">
                            <div class="text-sm font-bold text-gray-200">{len(q2)} 則</div>
                            <div class="text-[11px] text-gray-500">Q2 評論量</div>
                        </div>
                    </div>
                    <div class="mt-3 h-2 rounded-full overflow-hidden" style="background:#e5edf5;">
                        <div class="h-full rounded-full" style="width:{min(100, max(8, _avg(q2) / 5 * 100)):.1f}%;background:{style['bar']};"></div>
                    </div>
                    <div class="mt-2 text-[11px] text-gray-500">1★ 佔 Q2 {one_star_pct:.1f}%</div>
                </div>""")
        for label, count in _issue_tags(q2, limit=4):
            issue_cloud.append((summary.label, style["tag"], label, count))

    issue_cloud.sort(key=lambda item: item[3], reverse=True)
    tag_items = "\n".join(
        f'<span class="text-xs {tag_class} px-2.5 py-1 rounded-full">{brand} · {_html_escape(label)} {count}</span>'
        for brand, tag_class, label, count in issue_cloud[:10]
    )

    monthly = _monthly_stats(q2_rows_all)
    q2_total_count = sum(item["count"] for item in monthly) or 1
    monthly_rows = "\n".join(
        f"""
                    <div class="grid grid-cols-[3.25rem_1fr_4.5rem] items-center gap-3">
                        <span class="text-xs text-gray-400 font-semibold">{item['label']}</span>
                        <div class="h-3 rounded-full overflow-hidden" style="background:#e5edf5;">
                            <div class="h-full rounded-full" style="width:{item['count'] / q2_total_count * 100:.1f}%;background:linear-gradient(90deg,#635bff 0%,#c4b5fd 52%,#f96bee 100%);"></div>
                        </div>
                        <span class="text-xs text-gray-300 text-right">{item['count']} 則 · {_fmt(item['avg'])}★</span>
                    </div>"""
        for item in monthly
    )

    q2_avg = _avg(q2_rows_all)
    q2_negative = sum(1 for row in q2_rows_all if row[2] <= 2)
    q2_negative_pct = q2_negative / len(q2_rows_all) * 100 if q2_rows_all else 0
    yuanta_q2 = _avg(_quarter_rows(by_key["yuanta"], "q2"))
    sinopac_q2 = _avg(_quarter_rows(by_key["sinopac"], "q2"))
    cathay_q2 = _avg(_quarter_rows(by_key["cathay"], "q2"))

    return f"""
    <!-- AUTO_COMPACT_SUMMARY_START -->
    <section class="glass-card rounded-2xl p-5 md:p-6 border border-white/10">
        <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5">
            <div class="max-w-3xl">
                <div class="flex flex-wrap items-center gap-2 mb-3">
                    <span class="text-xs text-gray-500">更新 {latest_update} · 評論至 {latest_review}</span>
                </div>
                <h2 class="text-xl md:text-2xl font-extrabold text-white tracking-tight">Q2 評論關鍵判讀</h2>
                <p class="text-sm text-gray-400 mt-2 leading-relaxed">
                    元大 Q2 平均為 <strong class="text-blue-300">{_fmt(yuanta_q2)}★</strong>，6 月負評抵消修復紅利；
                    永豐以 <strong class="text-amber-300">{_fmt(sinopac_q2)}★</strong> 領先但耗電與開盤穩定仍是風險；
                    國泰降至 <strong class="text-rose-300">{_fmt(cathay_q2)}★</strong>，系統穩定與下單問題最集中。
                </p>
            </div>
            <div class="grid grid-cols-3 gap-3 min-w-full lg:min-w-[24rem]">
                <div class="rounded-xl bg-gray-950/50 border border-white/10 p-3">
                    <div class="text-2xl font-extrabold text-white">{total}</div>
                    <div class="text-[11px] text-gray-500">總評論</div>
                </div>
                <div class="rounded-xl bg-gray-950/50 border border-white/10 p-3">
                    <div class="text-2xl font-extrabold text-white">{_fmt(q2_avg)}</div>
                    <div class="text-[11px] text-gray-500">Q2 均分</div>
                </div>
                <div class="rounded-xl bg-gray-950/50 border border-white/10 p-3">
                    <div class="text-2xl font-extrabold text-white">{q2_negative_pct:.0f}%</div>
                    <div class="text-[11px] text-gray-500">Q2 低分率</div>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-5">
{''.join(brand_cards)}
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-5 gap-5 mt-5">
            <div class="lg:col-span-3 rounded-xl border border-white/10 bg-gray-950/35 p-4">
                <div class="flex items-center justify-between gap-3 mb-3">
                    <h3 class="text-sm font-bold text-gray-100">Q2 月度評論趨勢</h3>
                    <span class="text-[11px] text-gray-500">長條 = 評論量，右側 = 月均分</span>
                </div>
                <div class="space-y-3">
{monthly_rows}
                </div>
            </div>
            <div class="lg:col-span-2 rounded-xl border border-white/10 bg-gray-950/35 p-4">
                <h3 class="text-sm font-bold text-gray-100 mb-3">高頻議題標籤</h3>
                <div class="flex flex-wrap gap-2">
                    {tag_items}
                </div>
            </div>
        </div>
    </section>
    <!-- AUTO_COMPACT_SUMMARY_END -->"""


def _replace_compact_summary(content: str, summaries: list[AppSummary]) -> str:
    block = _compact_summary_html(summaries)
    pattern = r"\s*<!-- AUTO_COMPACT_SUMMARY_START -->.*?<!-- AUTO_COMPACT_SUMMARY_END -->"
    if re.search(pattern, content, flags=re.DOTALL):
        return re.sub(pattern, "\n" + block, content, count=1, flags=re.DOTALL)
    return content.replace(
        '<div id="content-dashboard" class="space-y-8">',
        '<div id="content-dashboard" class="space-y-8">\n' + block,
        1,
    )


def _star_class(q2_value: float, q1_value: float, neutral: str = "text-yellow-400") -> str:
    if q2_value > q1_value:
        return "text-green-400"
    if q2_value < q1_value:
        return "text-red-400"
    return neutral


def _replace_metric_card(content: str, title: str, q1_value: float, q2_value: float, star_class: str) -> str:
    pattern = (
        rf"(<span class=\"text-gray-400 text-xs font-semibold tracking-wider uppercase\">{re.escape(title)}</span>\s*)"
        r"<span class=\"text-xs font-bold tag-green px-2\.5 py-1 rounded-lg\">.*?</span>"
        r"(.*?<div class=\"text-xs text-gray-500 mb-0\.5\">Q1 平均</div>\s*)"
        r"<div class=\"text-3xl font-bold text-gray-400\">.*?<span class=\"text-base\">★</span></div>"
        r"(.*?<div class=\"text-xs text-gray-400 mb-0\.5\">Q2 平均</div>\s*)"
        r"<div class=\"text-5xl font-extrabold text-white\">.*?<span class=\"text-xl text-[\w-]+\">★</span></div>"
    )
    replacement = (
        f"\\1<span class=\"text-xs font-bold tag-green px-2.5 py-1 rounded-lg\">{_delta(q1_value, q2_value)}</span>"
        f"\\2<div class=\"text-3xl font-bold text-gray-400\">{_fmt(q1_value)} <span class=\"text-base\">★</span></div>"
        f"\\3<div class=\"text-5xl font-extrabold text-white\">{_fmt(q2_value)} <span class=\"text-xl {star_class}\">★</span></div>"
    )
    return re.sub(pattern, replacement, content, count=1, flags=re.DOTALL)


def _replace_competitor_card(content: str, heading: str, st: dict, total: int) -> str:
    pattern = (
        rf"(<h3 class=\"text-xl font-bold mt-1\.5 gradient-text-[a-z]+\">{re.escape(heading)}</h3>.*?"
        r"<div class=\"text-xs text-gray-500 mb-0\.5\">雙平台 Q2 趨勢</div>\s*)"
        r"<span class=\"text-sm font-bold text-[\w-]+\">.*?</span>"
        r"(.*?<div class=\"text-\[10px\] text-[\w-]+ font-bold uppercase\">雙平台合併</div>\s*)"
        r"<div class=\"text-xs text-gray-500\">Q1: <span class=\"text-gray-300 font-semibold\">.*?</span></div>\s*"
        r"<div class=\"text-sm font-extrabold text-white\">.*?<span class=\"text-xs text-[\w-]+\">★</span></div>\s*"
        r"<div class=\"text-\[10px\] text-gray-500\">（共 \d+ 則）</div>"
        r"(.*?<div class=\"text-\[10px\] text-green-400 font-bold uppercase\">Google Play</div>\s*)"
        r"<div class=\"text-xs text-gray-500\">Q1: <span class=\"text-gray-300 font-semibold\">.*?</span></div>\s*"
        r"<div class=\"text-sm font-extrabold text-white\">.*?<span class=\"text-xs text-green-400\">★</span></div>\s*"
        r"<div class=\"text-\[10px\] text-[\w-]+ font-bold\">.*?</div>"
        r"(.*?<div class=\"text-\[10px\] text-purple-400 font-bold uppercase\">App Store</div>\s*)"
        r"<div class=\"text-xs text-gray-500\">Q1: <span class=\"text-gray-300 font-semibold\">.*?</span></div>\s*"
        r"<div class=\"text-sm font-extrabold text-white\">.*?<span class=\"text-xs text-purple-400\">★</span></div>\s*"
        r"<div class=\"text-\[10px\] text-[\w-]+ font-bold\">.*?</div>"
    )
    trend_class = "text-green-400" if st["q2_avg"] >= st["q1_avg"] else "text-red-500"
    gp_delta_class = "text-green-400" if st["q2_gp"] >= st["q1_gp"] else "text-red-500"
    as_delta_class = "text-green-400" if st["q2_as"] >= st["q1_as"] else "text-red-500"
    replacement = (
        f"\\1<span class=\"text-sm font-bold {trend_class}\">{_delta(st['q1_avg'], st['q2_avg'])}</span>"
        f"\\2<div class=\"text-xs text-gray-500\">Q1: <span class=\"text-gray-300 font-semibold\">{_fmt(st['q1_avg'])} ★</span></div>"
        f"\n                        <div class=\"text-sm font-extrabold text-white\">{_fmt(st['q2_avg'])} <span class=\"text-xs text-yellow-400\">★</span></div>"
        f"\n                        <div class=\"text-[10px] text-gray-500\">（共 {total} 則）</div>"
        f"\\3<div class=\"text-xs text-gray-500\">Q1: <span class=\"text-gray-300 font-semibold\">{_fmt(st['q1_gp'])} ★</span></div>"
        f"\n                        <div class=\"text-sm font-extrabold text-white\">{_fmt(st['q2_gp'])} <span class=\"text-xs text-green-400\">★</span></div>"
        f"\n                        <div class=\"text-[10px] {gp_delta_class} font-bold\">{_delta(st['q1_gp'], st['q2_gp'])}</div>"
        f"\\4<div class=\"text-xs text-gray-500\">Q1: <span class=\"text-gray-300 font-semibold\">{_fmt(st['q1_as'])} ★</span></div>"
        f"\n                        <div class=\"text-sm font-extrabold text-white\">{_fmt(st['q2_as'])} <span class=\"text-xs text-purple-400\">★</span></div>"
        f"\n                        <div class=\"text-[10px] {as_delta_class} font-bold\">{_delta(st['q1_as'], st['q2_as'])}</div>"
    )
    return re.sub(pattern, replacement, content, count=1, flags=re.DOTALL)


def _replace_summary_text(content: str, summaries: list[AppSummary]) -> str:
    counts = {s.key: s.total for s in summaries}
    total = sum(counts.values())
    latest_update = max(s.updated_at for s in summaries)
    latest_review = max(s.latest_review_date for s in summaries)

    period = f"2026/01/01–{latest_review.strftime('%Y/%m/%d')}"
    update_date = latest_update.strftime("%Y-%m-%d")
    summary = (
        f"分析週期：{period}｜三大券商雙平台全量統計"
        f"（元大 {counts['yuanta']} 則、永豐 {counts['sinopac']} 則、"
        f"國泰 {counts['cathay']} 則，共計 {total} 則評論）"
    )
    source = (
        "資料來源：三大券商官方 Google Play + App Store 雙平台真實用戶評論全量統計"
        f"（元大 {counts['yuanta']} 則、永豐 {counts['sinopac']} 則、"
        f"國泰 {counts['cathay']} 則，總計 {total} 則評論）"
    )
    date_line = f"整理日期：{update_date} · 分析週期：{period}"

    content = re.sub(
        r"分析週期：[^<\n]+三大券商雙平台全量統計（元大 \d+ 則、永豐 \d+ 則、國泰 \d+ 則，共計 \d+ 則評論）",
        summary,
        content,
    )
    content = re.sub(
        r"資料更新：\d{4}-\d{2}-\d{2}",
        f"資料更新：{update_date}",
        content,
    )
    content = re.sub(
        r"資料來源：三大券商官方 Google Play \+ App Store 雙平台真實用戶評論全量統計（元大 \d+ 則、永豐 \d+ 則、國泰 \d+ 則，總計 \d+ 則評論）",
        source,
        content,
    )
    content = re.sub(
        r"整理日期：\d{4}-\d{2}-\d{2} · 分析週期：[^<\n]+",
        date_line,
        content,
    )
    content = re.sub(
        r"基於 \d+ 則真實用戶評論",
        f"基於 {total} 則真實用戶評論",
        content,
    )

    return content


def _replace_analysis_data(content: str, summaries: list[AppSummary]) -> str:
    by_key = {summary.key: summary for summary in summaries}
    yuanta = by_key["yuanta"]
    sinopac = by_key["sinopac"]
    cathay = by_key["cathay"]

    stats = {}
    for key, summary in by_key.items():
        q1 = _quarter_rows(summary, "q1")
        q2 = _quarter_rows(summary, "q2")
        stats[key] = {
            "q1": q1,
            "q2": q2,
            "q1_avg": _avg(q1),
            "q2_avg": _avg(q2),
            "q1_gp": _avg(q1, "Google Play"),
            "q2_gp": _avg(q2, "Google Play"),
            "q1_as": _avg(q1, "App Store"),
            "q2_as": _avg(q2, "App Store"),
            "q1_count": _count(q1),
            "q2_count": _count(q2),
            "q2_gp_count": _count(q2, "Google Play"),
            "q2_as_count": _count(q2, "App Store"),
        }

    y = stats["yuanta"]
    s = stats["sinopac"]
    c = stats["cathay"]
    y_total = y["q1_count"] + y["q2_count"]
    y_q1_pct = y["q1_count"] / y_total * 100
    y_q2_pct = y["q2_count"] / y_total * 100
    y_june = [row for row in y["q2"] if row[0].month == 6]
    s_june = [row for row in s["q2"] if row[0].month == 6]
    c_june = [row for row in c["q2"] if row[0].month == 6]
    y_june_low = sum(1 for row in y_june if row[2] <= 2)
    s_june_low = sum(1 for row in s_june if row[2] <= 2)
    c_june_low = sum(1 for row in c_june if row[2] <= 2)

    # Hero metric cards and competitor cards.
    metric_values = [
        (y["q1_avg"], y["q2_avg"]),
        (y["q1_gp"], y["q2_gp"]),
        (y["q1_as"], y["q2_as"]),
    ]
    for q1_value, q2_value in metric_values:
        content = _replace_once(
            content,
            r"<span class=\"text-xs font-bold tag-green px-2\.5 py-1 rounded-lg\">[↑↓] [+-]\d+\.\d+ ★</span>",
            f"<span class=\"text-xs font-bold tag-green px-2.5 py-1 rounded-lg\">{_delta(q1_value, q2_value)}</span>",
        )
        content = _replace_once(
            content,
            r"<div class=\"text-xs text-gray-500 mb-0\.5\">Q1 平均</div>\s*<div class=\"text-3xl font-bold text-gray-400\">\d+\.\d+ <span class=\"text-base\">★</span></div>",
            f"<div class=\"text-xs text-gray-500 mb-0.5\">Q1 平均</div>\n                        <div class=\"text-3xl font-bold text-gray-400\">{_fmt(q1_value)} <span class=\"text-base\">★</span></div>",
        )
        content = _replace_once(
            content,
            r"<div class=\"text-xs text-gray-400 mb-0\.5\">Q2 平均</div>\s*<div class=\"text-5xl font-extrabold text-white\">\d+\.\d+ <span class=\"text-xl text-[a-z-]+\">★</span></div>",
            lambda_match := f"<div class=\"text-xs text-gray-400 mb-0.5\">Q2 平均</div>\n                        <div class=\"text-5xl font-extrabold text-white\">{_fmt(q2_value)} <span class=\"text-xl text-yellow-400\">★</span></div>",
        )

    # Restore platform-specific colors for the second and third Q2 values.
    content = _replace_once(
        content,
        r"(<span class=\"text-xl text-yellow-400\">★</span></div>\s*</div>\s*</div>\s*<div class=\"mt-4 text-xs text-gray-400 flex items-center gap-1\.5\">\s*<span class=\"w-2 h-2 rounded-full bg-green-400 animate-pulse\"></span>Android)",
        r"<span class=\"text-xl text-green-400\">★</span></div>\n                    </div>\n                </div>\n                <div class=\"mt-4 text-xs text-gray-400 flex items-center gap-1.5\">\n                    <span class=\"w-2 h-2 rounded-full bg-green-400 animate-pulse\"></span>Android",
    )
    content = _replace_once(
        content,
        r"(<span class=\"text-xl text-yellow-400\">★</span></div>\s*</div>\s*</div>\s*<div class=\"mt-4 text-xs text-gray-400 flex items-center gap-1\.5\">\s*<span class=\"w-2 h-2 rounded-full bg-green-400 animate-pulse\"></span>手勢)",
        r"<span class=\"text-xl text-purple-400\">★</span></div>\n                    </div>\n                </div>\n                <div class=\"mt-4 text-xs text-gray-400 flex items-center gap-1.5\">\n                    <span class=\"w-2 h-2 rounded-full bg-green-400 animate-pulse\"></span>手勢",
    )

    # Competitor cards.
    for key, st in [("sinopac", s), ("cathay", c)]:
        content = _replace_once(
            content,
            r"<span class=\"text-sm font-bold text-red-[45]00\">[↑↓] [+-]\d+\.\d+ ★</span>",
            f"<span class=\"text-sm font-bold text-{'green-400' if st['q2_avg'] >= st['q1_avg'] else 'red-500'}\">{_delta(st['q1_avg'], st['q2_avg'])}</span>",
        )
        for q1_value, q2_value, count_value in [
            (st["q1_avg"], st["q2_avg"], st["q1_count"] + st["q2_count"]),
            (st["q1_gp"], st["q2_gp"], None),
            (st["q1_as"], st["q2_as"], None),
        ]:
            content = _replace_once(
                content,
                r"Q1: <span class=\"text-gray-300 font-semibold\">\d+\.\d+ ★</span></div>\s*<div class=\"text-sm font-extrabold text-white\">\d+\.\d+ <span class=\"text-xs text-[a-z-]+\">★</span></div>",
                f"Q1: <span class=\"text-gray-300 font-semibold\">{_fmt(q1_value)} ★</span></div>\n                        <div class=\"text-sm font-extrabold text-white\">{_fmt(q2_value)} <span class=\"text-xs text-yellow-400\">★</span></div>",
            )
            if count_value is not None:
                content = _replace_once(
                    content,
                    r"<div class=\"text-\[10px\] text-gray-500\">（共 \d+ 則）</div>",
                    f"<div class=\"text-[10px] text-gray-500\">（共 {count_value} 則）</div>",
                )
            else:
                content = _replace_once(
                    content,
                    r"<div class=\"text-\[10px\] text-[a-z-]+ font-bold\">[↑↓] [+-]\d+\.\d+ ★</div>",
                    f"<div class=\"text-[10px] text-{'green-400' if q2_value >= q1_value else 'red-500'} font-bold\">{_delta(q1_value, q2_value)}</div>",
                )

    # Chart legends, helper copy, and section badges.
    content = re.sub(r"Q1 \(\d+則\)", f"Q1 ({y['q1_count']}則)", content)
    content = re.sub(r"Q2 \(\d+則\)", f"Q2 ({y['q2_count']}則)", content)
    content = re.sub(r"雙平台合計 \d+ 則", f"雙平台合計 {y_total} 則", content)
    content = re.sub(r"Q1 \d+\.\d+%", f"Q1 {y_q1_pct:.1f}%", content)
    content = re.sub(r"Q2 \d+\.\d+%", f"Q2 {y_q2_pct:.1f}%", content)
    content = re.sub(
        r'(<span class="text-xs tag-amber px-2\.5 py-0\.5 rounded-full">)雙平台全量共 \d+ 則(</span>)',
        rf"\1雙平台全量共 {sinopac.total} 則\2",
        content,
    )
    content = re.sub(
        r'(<span class="text-xs tag-rose px-2\.5 py-0\.5 rounded-full">)雙平台全量共 \d+ 則(</span>)',
        rf"\1雙平台全量共 {cathay.total} 則\2",
        content,
    )

    # Trend insight prose.
    content = re.sub(
        r"iOS [+-]\d+\.\d+\s*★、Android [+-]\d+\.\d+\s*★，Q2 雙平台(?:均上揚|僅 [+-]\d+\.\d+\s*★| [+-]\d+\.\d+\s*★)。[^<]+",
        (
            f"iOS {_delta(y['q1_as'], y['q2_as']).replace('↑ ', '').replace('↓ ', '')}、"
            f"Android {_delta(y['q1_gp'], y['q2_gp']).replace('↑ ', '').replace('↓ ', '')}，"
            f"Q2 雙平台 {_delta(y['q1_avg'], y['q2_avg']).replace('↑ ', '').replace('↓ ', '')}。"
            "K 線修復後仍被 6 月卡頓、期貨停損、開戶與質押流程負評稀釋，改善幅度有限。"
        ),
        content,
    )
    content = re.sub(
        r"Q2 (?:[+-]\d+\.\d+★ 主因是 4 月正評增加；但 5 月仍有 11\+ 則 1★ 反映耗電過熱，若持續無解，下半年評分恐回落。|雙平台 [+-]\d+\.\d+\s*★，App Store 拉升至 \d+\.\d+★，但 Google Play 從 \d+\.\d+★ 回落至 \d+\.\d+★；耗電過熱與開盤穩定度仍是下半年風險。)",
        (
            f"Q2 雙平台 {_delta(s['q1_avg'], s['q2_avg']).replace('↑ ', '').replace('↓ ', '')}，"
            f"App Store 拉升至 {_fmt(s['q2_as'])}★，但 Google Play 從 {_fmt(s['q1_gp'])}★ 回落至 {_fmt(s['q2_gp'])}★；"
            "耗電過熱與開盤穩定度仍是下半年風險。"
        ),
        content,
    )
    content = re.sub(
        r"(?:2026 年 4 月市場劇烈波動期間，系統大規模崩潰引爆大量 1★ 評論。客服失聯的投訴更從 4 月持續至 5 月。|Q2 雙平台 [+-]\d+\.\d+\s*★，Google Play 僅 \d+\.\d+★、App Store \d+\.\d+★。4 月至 6 月仍集中在系統當機、報價連線、客服量能與字體/版面問題。)",
        (
            f"Q2 雙平台 {_delta(c['q1_avg'], c['q2_avg']).replace('↑ ', '').replace('↓ ', '')}，"
            f"Google Play 僅 {_fmt(c['q2_gp'])}★、App Store {_fmt(c['q2_as'])}★。"
            "4 月至 6 月仍集中在系統當機、報價連線、客服量能與字體/版面問題。"
        ),
        content,
    )

    # Chart.js datasets.
    y_q1_dist = _dist_5_to_1(y["q1"])
    y_q2_dist = _dist_5_to_1(y["q2"])
    content = re.sub(r"label: 'Q1 \(共 \d+ 則\)'", f"label: 'Q1 (共 {y['q1_count']} 則)'", content)
    content = re.sub(r"label: 'Q2 \(共 \d+ 則\)'", f"label: 'Q2 (共 {y['q2_count']} 則)'", content)
    content = _replace_once(content, r"data: \[\d+, \d+, \d+, \d+, \d+\]", f"data: {y_q1_dist}")
    content = _replace_once(content, r"data: \[\d+, \d+, \d+, \d+, \d+\]", f"data: {y_q2_dist}")
    content = re.sub(r"ctx\.datasetIndex === 0 \? \d+ : \d+", f"ctx.datasetIndex === 0 ? {y['q1_count']} : {y['q2_count']}", content)
    content = _replace_once(
        content,
        r"data: \[\d+\.\d+, \d+\.\d+, \d+\.\d+\]",
        f"data: [{_fmt(y['q1_avg'])}, {_fmt(s['q1_avg'])}, {_fmt(c['q1_avg'])}]",
    )
    content = _replace_once(
        content,
        r"data: \[\d+\.\d+, \d+\.\d+, \d+\.\d+\]",
        f"data: [{_fmt(y['q2_avg'])}, {_fmt(s['q2_avg'])}, {_fmt(c['q2_avg'])}]",
    )
    content = re.sub(r"data: \[\d+, \d+\]", f"data: [{y['q1_count']}, {y['q2_count']}]", content)
    content = re.sub(r"ctx\.raw / \d+", f"ctx.raw / {y_total}", content)

    # Final title-scoped overrides keep repeated card structures from drifting.
    content = _replace_metric_card(content, "雙平台合併平均評分", y["q1_avg"], y["q2_avg"], "text-yellow-400")
    content = _replace_metric_card(content, "Google Play 平均評分", y["q1_gp"], y["q2_gp"], "text-green-400")
    content = _replace_metric_card(content, "App Store 平均評分", y["q1_as"], y["q2_as"], "text-purple-400")
    content = _replace_competitor_card(content, "大戶投 App", s, sinopac.total)
    content = _replace_competitor_card(content, "國泰證券 App", c, cathay.total)

    content = re.sub(
        r"data: \[[0-9, ]+\](?=,\s*backgroundColor: 'rgba\((?:59,130,246|83,58,253|99,91,255),0\.(?:72|75)\)')",
        f"data: {y_q1_dist}",
        content,
    )
    content = re.sub(
        r"data: \[[0-9, ]+\](?=,\s*backgroundColor: 'rgba\((?:52,211,153|234,34,97|249,107,238),0\.(?:68|75)\)')",
        f"data: {y_q2_dist}",
        content,
    )
    content = re.sub(
        r"data: \[[0-9.]+, [0-9.]+, [0-9.]+\](?=,\s*backgroundColor: \['rgba\((?:59,130,246|83,58,253|99,91,255),0\.(?:42|55)\)')",
        f"data: [{_fmt(y['q1_avg'])}, {_fmt(s['q1_avg'])}, {_fmt(c['q1_avg'])}]",
        content,
    )
    content = re.sub(
        r"data: \[[0-9.]+, [0-9.]+, [0-9.]+\](?=,\s*backgroundColor: \['rgba\((?:96,165,250|83,58,253|99,91,255),0\.(?:82|85)\)')",
        f"data: [{_fmt(y['q2_avg'])}, {_fmt(s['q2_avg'])}, {_fmt(c['q2_avg'])}]",
        content,
    )

    content = re.sub(
        r"元大：唯一持續改善的券商 App",
        "元大：Q2 幾乎持平，6 月負評稀釋修復紅利",
        content,
    )
    content = re.sub(
        r"元大：Q2 幾乎持平，6 月負評稀釋修復紅利",
        "元大：Q2 小幅下滑，6 月負評稀釋修復紅利",
        content,
    )
    content = re.sub(
        r"Q2 整體滿意度小幅回升",
        "Q2 6 月負評使整體小幅回落",
        content,
    )
    content = re.sub(
        r"Android 評分拉回 3\.0 星大關",
        "Android 評分小幅回升但仍未回 3 星",
        content,
    )
    content = re.sub(
        r"Android 評分小幅回升但仍未回 3 星",
        "Android 評分小幅回落且仍未回 3 星",
        content,
    )
    content = re.sub(
        r"國泰：Q2 急跌 −0\.33★，4 月崩機事件是主因",
        f"國泰：Q2 急跌 {_delta(c['q1_avg'], c['q2_avg']).replace('↓ ', '')}，系統穩定仍是主因",
        content,
    )
    content = re.sub(
        r"title: '國泰證券：Q2 急跌 −0\.33★'",
        f"title: '國泰證券：Q2 急跌 {_delta(c['q1_avg'], c['q2_avg']).replace('↓ ', '')}'",
        content,
    )
    content = re.sub(
        r"title: '國泰證券：Q2 急跌 [+-]\d+\.\d+ ★'",
        f"title: '國泰證券：Q2 急跌 {_delta(c['q1_avg'], c['q2_avg']).replace('↓ ', '')}'",
        content,
    )
    content = re.sub(
        r"subtitle: '4 月崩機事件 · 大量 1★ 集中爆發 · 客服失聯'",
        "subtitle: '4–6 月系統當機、報價連線與客服量能問題持續'",
        content,
    )
    content = re.sub(
        r"subtitle: '代表性正面改善評論 · K 線修復是主驅動力'",
        "subtitle: 'K 線修復後仍受 6 月登入、持有成本、閃電下單鎖定與開戶補件負評抵消'",
        content,
    )
    content = re.sub(
        r"subtitle: '正評增加同時 5月高頻耗電投訴未減'",
        "subtitle: 'App Store 正評拉升，但 Android 開盤穩定與耗電問題仍拖累'",
        content,
    )

    # Lower-page analysis copy that is not covered by the top summary sync.
    content = re.sub(r"Q2 核心痛點（4–5月）", "Q2 核心痛點（4–6月）", content)
    content = re.sub(r"主要版本：4\.16 – 4\.17", "主要版本：4.16 – 4.18", content)
    content = re.sub(
        r"4\.15\.0 版本引入 K 線右滑手勢衝突，滑動K線即跳回清單頁，4\.16\.0 修復。然而 4\.17\.0（5/7）更新後，庫存頁圓餅圖百分比字體縮小，引發新一波使用者投訴。",
        (
            "4.15.0 版本引入 K 線右滑手勢衝突，4.16.0 修復後，4.17.0 的庫存圓餅圖字體縮小與動線異動延續負評；"
            f"6 月 4.18.x 又出現登入、開戶自拍補件、持有成本與閃電下單鎖定等新痛點，6 月低分評論 {y_june_low} 則。"
        ),
        content,
    )
    content = re.sub(
        r"4\.16\.0 順利修復 K 線滑動衝突。但 5/7 的 4\.17\.0 將庫存頁面圓餅圖百分比數字改得極小，遭到大量投訴。",
        (
            "4.16.0 修復 K 線滑動衝突後，4.17.0 的庫存圓餅圖字體與動線異動延續負評；"
            f"6 月 4.18.x 又出現登入、開戶自拍補件、持有成本與閃電下單鎖定等新痛點，6 月低分評論 {y_june_low} 則。"
        ),
        content,
    )
    content = re.sub(
        r"三家 App 均有用戶反映 9 點開盤後出現延遲、崩潰或連線異常。國泰 Q2 因此問題最為嚴重，評分急跌。",
        (
            "三家 App 均有用戶反映 9 點開盤後出現延遲、崩潰或連線異常。"
            f"6 月低分評論元大 {y_june_low} 則、永豐 {s_june_low} 則、國泰 {c_june_low} 則，國泰 Q2 仍是最嚴重者。"
        ),
        content,
    )
    content = re.sub(
        r"元大 Q1 手勢衝突、永豐 Q1 K 線閃爍，均因更新引入圖表層面 Bug。圖表是券商 App 的核心功能，Bug 容忍度接近零。",
        (
            "元大 Q1 手勢衝突、永豐 Q1 K 線閃爍，到 6 月又延伸為美股 K 線空畫面、成本/持有資訊與圖表還原除息異常。"
            "圖表與帳務數據是券商 App 的核心信任層，Bug 容忍度接近零。"
        ),
        content,
    )
    content = re.sub(
        r"元大 K 線手勢衝突修復後，4\.17\.0 版本又因「字體縮小、強制塞入客服、當沖快捷鍵被砍」激起排斥潮；而國泰當機引發用戶巨大焦慮；永豐深色配色偏暗且功能碎片化。",
        (
            "元大 K 線手勢衝突修復後，4.17.0 的字體與動線問題延續到 4.18.x 的登入、持有成本、閃電下單鎖定與開戶補件摩擦；"
            "國泰當機與下單延遲引發用戶焦慮；永豐則在介面細節、耗電與開盤穩定度間拉扯。"
        ),
        content,
    )
    content = re.sub(
        r"分析國泰與永豐開盤 API 卡頓；元大 4\.17\.0 每 30 秒登出 Bug 是 Load Balancer 與心跳設置異常；建議開戶增加 LocalStorage 暫存防呆，並優化前端渲染降低能耗。",
        (
            "分析國泰與永豐開盤 API 卡頓；元大 4.18.x 新增登入、開戶自拍補件、持有成本顯示與閃電下單鎖定問題，顯示交易狀態、Session 與帳務資料同步仍需治理；"
            "建議開戶增加暫存防呆，並優化前端渲染與交易狀態回復。"
        ),
        content,
    )
    content = re.sub(
        r"元大 Q1 手勢衝突 Bug 簡直是災難，用戶甚至以為是螢幕貼壞掉，撕掉保護貼才發現是 App 導航手勢衝突！雖然 Q2 修復了，但 4\.17\.0 版本又將庫存圓餅圖阿拉伯數字報酬率改得極小，且塞入浮動客服、砍掉當沖快捷跳轉，這是一次典型的『產品中心』對『用戶體驗』的傷害。",
        (
            "元大 Q1 手勢衝突 Bug 修復後，Q2 沒有真正形成口碑反彈；4.17.0 的庫存圓餅圖字體與動線異動，"
            "加上 4.18.x 的登入、持有成本、閃電下單鎖定與開戶自拍補件問題，讓使用者感覺核心任務仍被打斷。"
        ),
        content,
    )
    content = re.sub(
        r"元大 Q1 手勢衝突 Bug 簡集是災難，用戶甚至以為是螢幕貼壞掉，撕掉保護貼才發現是 App 導航手勢衝突！雖然 Q2 修復了，但 4\.17\.0 版本又將庫存圓餅圖阿拉伯數字報酬率改得極小，且塞入浮動客服、砍掉當沖快捷跳轉，這是一次典型的『產品中心』對『用戶體驗』的傷害。",
        (
            "元大 Q1 手勢衝突 Bug 修復後，Q2 沒有真正形成口碑反彈；4.17.0 的庫存圓餅圖字體與動線異動，"
            "加上 4.18.x 的登入、持有成本、閃電下單鎖定與開戶自拍補件問題，讓使用者感覺核心任務仍被打斷。"
        ),
        content,
    )
    content = re.sub(
        r"元大 4\.17\.0 則出現了『每 30 秒強制自動登出』以及『行動網路極卡、WiFi 正常』的相容性異常。",
        "元大 4.18.x 則出現登入、身分驗證補件、持有成本顯示與閃電下單鎖定狀態無法保持等相容性與狀態同步異常。",
        content,
    )
    content = re.sub(
        r"但支撐這個定位的前提是修復自己 4\.17\.0 版的字體和當沖路徑。",
        "但支撐這個定位的前提是修復 4.18.x 版的登入、持有成本、閃電下單與開戶補件路徑。",
        content,
    )
    content = re.sub(
        r"🔴 4\.17\.0 圓餅圖數字字體變極小；移除當沖快捷鍵；新增客服懸浮標誌增加誤觸。",
        "🔴 4.17.0 圓餅圖字體與動線異動；4.18.x 登入、持有成本、開戶補件與閃電下單鎖定狀態引發新負評。",
        content,
    )
    content = re.sub(
        r"🔴 4\.17\.0 開盤 Session 強制登出 Bug；行動網路相容性較差。",
        "🔴 4.18.x 登入/身分驗證、交易狀態保持與帳務資料同步仍有穩定性風險。",
        content,
    )
    content = re.sub(
        r"title: '元大投資先生：Q2 評分回升'",
        "title: '元大投資先生：Q2 評分小幅下滑'",
        content,
    )
    content = re.sub(
        r"title: '元大投資先生：Q2 K線修復後字體縮小爭議'",
        "title: '元大投資先生：版本迭代引發 K 線操作異常，修復後介面元素縮小惹議'",
        content,
    )
    content = re.sub(
        r"title: '元大投資先生：Q2 浮動客服 \+ 當沖快捷遭移除'",
        "title: '元大投資先生：功能持續擴增導致操作動線複雜化，彈窗設計干擾交易流程'",
        content,
    )
    content = re.sub(
        r"title: '元大投資先生：線上開戶切換 App 即清空'",
        "title: '元大投資先生：線上開戶缺乏跨 App 狀態保存機制，切換即觸發資料清除'",
        content,
    )
    content = re.sub(
        r"subtitle: '4\.15\.0 K線手勢衝突 → 4\.16\.0 修復 → 4\.17\.0 圓餅圖字體縮小 · Q2 共約 13 則'",
        "subtitle: '4.17.0 圓餅圖字體與動線異動 → 4.18.x 登入、持有成本、閃電下單鎖定與開戶補件 · Q2 持續'",
        content,
    )
    content = re.sub(
        r"subtitle: '4\.17\.0 版本 · 圓餅圖百分比字體極小'",
        "subtitle: '4.17.0 字體與動線異動 → 4.18.x 登入、成本、閃電下單鎖定與開戶補件'",
        content,
    )
    content = re.sub(
        r"subtitle: '4\.15\.0–4\.17\.0 累積 · 投資夥伴 / 強制彈窗 / 導覽動線失當 · Q2 共約 17 則'",
        "subtitle: '4.15.0–4.18.x 累積 · 投資夥伴 / 強制彈窗 / 導覽動線 / 核心交易路徑干擾 · Q2 持續'",
        content,
    )
    content = re.sub(
        r"subtitle: '4\.17\.0 版本 · 投資夥伴塞入 · 誤觸客服圖標 · 當沖路徑砍掉'",
        "subtitle: '4.15.0–4.18.x 累積 · 投資夥伴 / 強制彈窗 / 導覽動線 / 核心交易路徑干擾'",
        content,
    )
    content = re.sub(
        r"subtitle: '4\.16\.1 版本 · Android 後台記憶體回收 / 跨 App 切換 · Q2 共 4 則'",
        "subtitle: '4.16.1–4.18.x 版本 · Android 後台記憶體回收 / 跨 App 切換 / 登入狀態保持 · Q2 持續'",
        content,
    )

    return content


def refresh_static_summaries() -> None:
    """同步 index.html 與 Yuanta_Reviews_Dashboard.html 的頂部/頁尾統計摘要。"""
    summaries = [
        _read_summary("yuanta", "元大", "Yuanta_App_Reviews.md"),
        _read_summary("sinopac", "永豐", "SinoPac_App_Reviews.md"),
        _read_summary("cathay", "國泰", "Cathay_App_Reviews.md"),
    ]

    for html_name in ["index.html", "Yuanta_Reviews_Dashboard.html"]:
        html_path = Path(config.BASE_DIR) / html_name
        if not html_path.exists():
            continue
        original = html_path.read_text(encoding="utf-8")
        updated = _replace_summary_text(original, summaries)
        updated = _replace_analysis_data(updated, summaries)
        updated = _replace_compact_summary(updated, summaries)
        updated = _replace_detail_reviews(updated, summaries)
        updated = _replace_stripe_chart_colors(updated)
        if updated != original:
            html_path.write_text(updated, encoding="utf-8")
            logger.info(f"  🧭 已同步首頁摘要：{html_name}")
        else:
            logger.info(f"  🧭 首頁摘要已是最新：{html_name}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    refresh_static_summaries()
