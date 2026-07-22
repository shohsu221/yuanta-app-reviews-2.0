"""
web_sync.py — Regenerate the data-driven parts of Yuanta_Reviews_Web.html from the
review Markdown files, in place.

Synced from the .md data:
  • `const allReviews = [...]`        — the review-browser dataset
  • yuantaStarChart / brandCompareChart / donutChart datasets
  • the three headline KPIs (總評論 / Q2 均分 / Q2 低分率)
  • the three brand cards (score, Q1→Q2 delta, Q2 count, 1★ share, track width)

Hand-authored narrative and insight prose (the "關鍵判讀" paragraph, competitor
cards, expert analysis, etc.) is intentionally left untouched — it is editorial,
not data. All numbers come from web_data.compute_stats(), the same computation
validate_dashboard.py checks against.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from crawler.utils import config
from crawler.sync import web_data

logger = logging.getLogger("scraper_agent")

WEB_HTML = web_data.WEB_HTML

# yuanta card is first, then sinopac, then cathay (see web_data.BRANDS order).
_CSS_INDEX = {css: i for i, (_, _, css) in enumerate(web_data.BRANDS)}


def _fmt_int_arr(values) -> str:
    return "[" + ",".join(str(int(v)) for v in values) + "]"


def _fmt_float_arr(values, decimals: int = 2) -> str:
    return "[" + ",".join(f"{v:.{decimals}f}" for v in values) + "]"


def _sub_once(html: str, pattern: str, replacement, what: str) -> str:
    """re.sub with count=1 that raises if the anchor is missing (fail loud, not silent)."""
    new_html, n = re.subn(pattern, replacement, html, count=1)
    if n != 1:
        raise ValueError(f"web_sync: expected exactly 1 match for {what}, found {n}")
    return new_html


def _sync_all_reviews(html: str, reviews: list[dict]) -> str:
    payload = web_data.all_reviews_json(reviews)
    # Single-line assignment; `.` (no DOTALL) keeps the match on that one line.
    return _sub_once(
        html,
        r"(const allReviews = )\[.*\](;)",
        lambda m: m.group(1) + payload + m.group(2),
        "allReviews array",
    )


def _chart_span(html: str, chart_id: str) -> tuple[int, int]:
    start = html.index(f"getElementById('{chart_id}')")
    nxt = html.find("new Chart(", start + 1)
    return start, (nxt if nxt != -1 else len(html))


def _replace_in_span(html: str, chart_id: str, pattern: str, new_array: str) -> str:
    start, end = _chart_span(html, chart_id)
    seg, n = re.subn(pattern, lambda m: m.group(1) + new_array, html[start:end], count=1)
    if n != 1:
        raise ValueError(f"web_sync: {chart_id} pattern {pattern!r} matched {n} times")
    return html[:start] + seg + html[end:]


def _sync_charts(html: str, s: dict) -> str:
    html = _replace_in_span(html, "yuantaStarChart", r"(label:'Q1',data:)\[[0-9.,\s]*\]",
                            _fmt_int_arr(s["yuanta_star_q1"]))
    html = _replace_in_span(html, "yuantaStarChart", r"(label:'Q2',data:)\[[0-9.,\s]*\]",
                            _fmt_int_arr(s["yuanta_star_q2"]))
    html = _replace_in_span(html, "brandCompareChart", r"(label:'Q1',data:)\[[0-9.,\s]*\]",
                            _fmt_float_arr(s["brand_q1_avg"]))
    html = _replace_in_span(html, "brandCompareChart", r"(label:'Q2',data:)\[[0-9.,\s]*\]",
                            _fmt_float_arr(s["brand_q2_avg"]))
    html = _replace_in_span(html, "donutChart", r"(datasets:\[\{data:)\[[0-9.,\s]*\]",
                            _fmt_int_arr(s["yuanta_donut"]))
    return html


def _sync_kpis(html: str, s: dict) -> str:
    html = _sub_once(
        html,
        r'(<div class="mn">)[0-9.]+(</div><div class="ml">總評論</div>)',
        lambda m: m.group(1) + str(s["total"]) + m.group(2),
        "KPI 總評論",
    )
    html = _sub_once(
        html,
        r'(<div class="mn">)[0-9.]+(</div><div class="ml">Q2 均分</div>)',
        lambda m: m.group(1) + f'{s["q2_avg"]:.2f}' + m.group(2),
        "KPI Q2 均分",
    )
    html = _sub_once(
        html,
        r'(<div class="mn"[^>]*>)[0-9.]+%(</div><div class="ml">Q2 低分率</div>)',
        lambda m: m.group(1) + f'{s["q2_low_pct"]}%' + m.group(2),
        "KPI Q2 低分率",
    )
    return html


# One brand card. Static structure is captured; the six numeric fields are rewritten.
_CARD_RE = re.compile(
    r'(?P<a><div class="bcard">\s*<div class="bhead"><span class="badge">'
    r'<span class="sw" style="background:var\(--(?P<css>\w+)\)"></span>'
    r'[^<]*</span><span class="delta )d[ud](?P<b>">)[^<]*'
    r'(?P<c></span></div>\s*<div class="score"><span class="s">)[0-9.]+'
    r'(?P<d></span><span class="st">★</span><span class="of">/5</span></div>\s*'
    r'<div class="meta-row"><span>)[0-9]+'
    r'(?P<e> 則 · Q2</span><span>1★ )[0-9.]+'
    r'(?P<f>%</span></div>\s*<div class="track"><i style="width:)[0-9.]+'
    r'(?P<g>%"></i>)'
)


def _sync_brand_cards(html: str, s: dict) -> str:
    def repl(m: re.Match) -> str:
        i = _CSS_INDEX[m.group("css")]
        q1, q2 = s["brand_q1_avg"][i], s["brand_q2_avg"][i]
        delta = round(q2 - q1, 2)
        klass = "du" if delta >= 0 else "dd"
        sign = "+" if delta >= 0 else "−"  # unicode minus, matching the design
        delta_txt = f"{sign}{abs(delta):.2f} ★"
        width = q2 / 5 * 100
        return (
            m.group("a") + klass + m.group("b") + delta_txt
            + m.group("c") + f"{q2:.2f}"
            + m.group("d") + str(s["brand_q2_count"][i])
            + m.group("e") + f'{s["brand_q2_1star_pct"][i]:.1f}'
            + m.group("f") + f"{width:.1f}"
            + m.group("g")
        )

    new_html, n = _CARD_RE.subn(repl, html)
    if n != len(web_data.BRANDS):
        raise ValueError(f"web_sync: expected {len(web_data.BRANDS)} brand cards, matched {n}")
    return new_html


# The three brand scores are also quoted inline in the hero paragraph. Only the
# numbers are data — the surrounding commentary stays hand-authored.
_NARRATIVE_SCORE = {"by": 0, "bs": 1, "bc": 2}


def _sync_narrative_scores(html: str, s: dict) -> str:
    for klass, i in _NARRATIVE_SCORE.items():
        html = _sub_once(
            html,
            rf'(<b class="{klass}">)[0-9.]+(★</b>)',
            lambda m, i=i: m.group(1) + f'{s["brand_q2_avg"][i]:.2f}' + m.group(2),
            f"narrative score .{klass}",
        )
    return html


def _subn(html: str, pattern: str, repl, what: str, n_expected: int = 1) -> str:
    """Replace all matches; raise unless exactly n_expected were found (fail loud)."""
    new_html, n = re.subn(pattern, repl, html)
    if n != n_expected:
        raise ValueError(f"web_sync: {what}: expected {n_expected} matches, got {n}")
    return new_html


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _slash(d: str) -> str:            # 2026-06-30 -> 2026/06/30
    return d.replace("-", "/")


def _a2(v: float) -> str:
    return f"{v:.2f}"


def _delta_star(d: float) -> tuple[str, str]:
    """(du|dd, '↑ +0.16 ★') — for the competitor trend badge."""
    up = d >= 0
    return ("du" if up else "dd"), f"{'↑' if up else '↓'} {'+' if up else '−'}{abs(d):.2f} ★"


def _delta_chg(d: float) -> tuple[str, str]:
    """(color, '↑ +0.53') — for the per-platform change cell."""
    up = d >= 0
    return ("var(--green)" if up else "var(--rose)"), f"{'↑' if up else '↓'} {'+' if up else '−'}{abs(d):.2f}"


def _sync_meta(html: str, s: dict) -> str:
    """Header subtitle, update dates, chart legends, donut, deep-dive totals."""
    today, newest, oldest = _today(), _slash(s["newest_date"]), _slash(s["oldest_date"])
    b = s["brand_total"]

    html = _subn(html, r'(分析週期 )\d{4}/\d{2}/\d{2}–\d{4}/\d{2}/\d{2}',
                 lambda m: f"{m.group(1)}{oldest}–{newest}", "header period")
    html = _subn(html, r'(元大 )\d+( 則 · 永豐 )\d+( 則 · 國泰 )\d+( 則，共計 )\d+( 則評論)',
                 lambda m: f"{m.group(1)}{b[0]}{m.group(2)}{b[1]}{m.group(3)}{b[2]}{m.group(4)}{sum(b)}{m.group(5)}",
                 "header brand counts")
    html = _subn(html, r'(資料更新 )\d{4}-\d{2}-\d{2}', lambda m: m.group(1) + today,
                 "資料更新 dates (badge + footer)", n_expected=2)
    html = _subn(html, r'(更新 )\d{4}-\d{2}-\d{2}( · 評論至 )\d{4}/\d{2}/\d{2}',
                 lambda m: f"{m.group(1)}{today}{m.group(2)}{newest}", "eyebrow update/coverage")
    html = _subn(html, r'(<i style="background:#c7c7cc"></i>Q1 \()\d+(則\))',
                 lambda m: m.group(1) + str(s["yuanta_donut"][0]) + m.group(2), "star legend Q1")
    html = _subn(html, r'(<i style="background:#0071e3"></i>Q2 \()\d+(則\))',
                 lambda m: m.group(1) + str(s["yuanta_donut"][1]) + m.group(2), "star legend Q2")
    html = _subn(html, r'(雙平台合計 )\d+( 則)',
                 lambda m: m.group(1) + str(b[0]) + m.group(2), "donut hint total")
    html = _subn(html, r'(border-radius:50%"></i>Q1 )[0-9.]+(%)',
                 lambda m: m.group(1) + f'{s["yuanta_q1_share"]:.1f}' + m.group(2), "donut Q1 share")
    html = _subn(html, r'(border-radius:50%"></i>Q2 )[0-9.]+(%)',
                 lambda m: m.group(1) + f'{s["yuanta_q2_share"]:.1f}' + m.group(2), "donut Q2 share")
    html = _subn(html, r'(永豐大戶投 痛點詳析</h3><span class="tg tga">雙平台全量共 )\d+( 則)',
                 lambda m: m.group(1) + str(b[1]) + m.group(2), "deep-dive sinopac total")
    html = _subn(html, r'(國泰證券 痛點詳析</h3><span class="tg tgr">雙平台全量共 )\d+( 則)',
                 lambda m: m.group(1) + str(b[2]) + m.group(2), "deep-dive cathay total")
    return html


def _competitor_card(block: str, s: dict, i: int) -> str:
    klass, trend = _delta_star(s["brand_delta"][i])
    block = _subn(block,
                  r'(雙平台 Q2 趨勢</div><span class="delta )d[ud](" style="[^"]*">)[↑↓] [+−][0-9.]+ ★(</span>)',
                  lambda m: m.group(1) + klass + m.group(2) + trend + m.group(3), "comp trend")
    block = _subn(block,
                  r'(雙平台合併</div><div class="q1">Q1 )[0-9.]+(★</div><div class="now">)[0-9.]+'
                  r'(<span[^>]*>★</span></div><div class="chg"[^>]*>共 )\d+( 則)',
                  lambda m: m.group(1) + _a2(s["brand_q1_avg"][i]) + m.group(2) + _a2(s["brand_q2_avg"][i])
                  + m.group(3) + str(s["brand_total"][i]) + m.group(4), "comp dual row")
    gpc, gpt = _delta_chg(s["brand_gp_delta"][i])
    block = _subn(block,
                  r'(Google Play</div><div class="q1">Q1 )[0-9.]+(★</div><div class="now">)[0-9.]+'
                  r'(★</div><div class="chg" style="color:)[^"]*(">)[↑↓] [+−][0-9.]+(</div>)',
                  lambda m: m.group(1) + _a2(s["brand_gp_q1_avg"][i]) + m.group(2) + _a2(s["brand_gp_q2_avg"][i])
                  + m.group(3) + gpc + m.group(4) + gpt + m.group(5), "comp GP row")
    asc, ast = _delta_chg(s["brand_as_delta"][i])
    block = _subn(block,
                  r'(App Store</div><div class="q1">Q1 )[0-9.]+(★</div><div class="now">)[0-9.]+'
                  r'(★</div><div class="chg" style="color:)[^"]*(">)[↑↓] [+−][0-9.]+(</div>)',
                  lambda m: m.group(1) + _a2(s["brand_as_q1_avg"][i]) + m.group(2) + _a2(s["brand_as_q2_avg"][i])
                  + m.group(3) + asc + m.group(4) + ast + m.group(5), "comp AS row")
    return block


def _sync_competitor(html: str, s: dict) -> str:
    """Competitor snapshot cards — 永豐 (index 1) and 國泰 (index 2)."""
    i_sino = html.index('<div class="comp amber">')
    i_cat = html.index('<div class="comp rose">')
    i_end = html.index('<div class="grid-charts">')
    sino = _competitor_card(html[i_sino:i_cat], s, 1)
    cat = _competitor_card(html[i_cat:i_end], s, 2)
    return html[:i_sino] + sino + cat + html[i_end:]


def _sync_tab2(html: str, s: dict) -> str:
    """Tab-2 review-list summary cards (whole-dataset per-brand stats)."""
    for tag, name, i in [("tgb", "元大投資先生", 0), ("tga", "永豐大戶投", 1), ("tgc", "國泰證券", 2)]:
        a = rf'<span class="tg {tag}">{name}</span>'
        html = _subn(html, rf'({a}<span class="meta-row" style="margin:0;color:var\(--meta\)">)\d+( 則)',
                     lambda m, i=i: m.group(1) + str(s["brand_total"][i]) + m.group(2), f"tab2 {tag} total")
        html = _subn(html, rf'(?s)({a}.*?<span class="s" style="font-size:30px">)[0-9.]+(</span>)',
                     lambda m, i=i: m.group(1) + _a2(s["brand_overall_avg"][i]) + m.group(2), f"tab2 {tag} avg")
        html = _subn(html, rf'(?s)({a}.*?<span>Google Play )\d+( · App Store )\d+(</span>)',
                     lambda m, i=i: m.group(1) + str(s["brand_gp_count"][i]) + m.group(2)
                     + str(s["brand_as_count"][i]) + m.group(3), f"tab2 {tag} platform split")
        html = _subn(html, rf'(?s)({a}.*?<div class="track"><i style="width:)[0-9.]+(%)',
                     lambda m, i=i: m.group(1) + f'{s["brand_overall_avg"][i] / 5 * 100:.1f}' + m.group(2),
                     f"tab2 {tag} width")
        html = _subn(html, rf'(?s)({a}.*?低分評論 )\d+( 則)',
                     lambda m, i=i: m.group(1) + str(s["brand_low12_count"][i]) + m.group(2), f"tab2 {tag} low12")
    return html


def _sign(d: float) -> str:
    """Plain signed 2dp: '+0.16' / '−0.46' (unicode minus, matching the prose)."""
    return f"{'+' if d >= 0 else '−'}{abs(d):.2f}"


def _metric_card(html: str, title: str, q1v: float, q2v: float, dv: float) -> str:
    kl, dt = _delta_star(dv)
    t = re.escape(title)
    html = _subn(html, rf'({t}</span><span class="delta )d[ud](">)[↑↓] [+−][0-9.]+ ★(</span>)',
                 lambda m: m.group(1) + kl + m.group(2) + dt + m.group(3), f"core {title} delta")
    html = _subn(html, rf'(?s)({t}.*?<div class="l">Q1 平均</div><div class="n">)[0-9.]+(★</div>)',
                 lambda m: m.group(1) + _a2(q1v) + m.group(2), f"core {title} Q1")
    html = _subn(html, rf'(?s)({t}.*?<div class="l">Q2 平均</div><div class="n">)[0-9.]+(<span[^>]*>★</span>)',
                 lambda m: m.group(1) + _a2(q2v) + m.group(2), f"core {title} Q2")
    return html


def _sync_core_metrics(html: str, s: dict) -> str:
    """元大投資先生 核心指標 — Yuanta dual/GP/AS Q1→Q2 averages + deltas (index 0)."""
    html = _metric_card(html, "雙平台合併平均評分", s["brand_q1_avg"][0], s["brand_q2_avg"][0], s["brand_delta"][0])
    html = _metric_card(html, "Google Play 平均評分", s["brand_gp_q1_avg"][0], s["brand_gp_q2_avg"][0], s["brand_gp_delta"][0])
    html = _metric_card(html, "App Store 平均評分", s["brand_as_q1_avg"][0], s["brand_as_q2_avg"][0], s["brand_as_delta"][0])
    return html


def _sync_monthly(html: str, s: dict) -> str:
    """元大 Q2 月度評論趨勢 — all-brand Q2 monthly count · avg · bar width."""
    for idx, mo in enumerate((4, 5, 6)):
        html = _subn(
            html,
            rf'(<span class="md">{mo}月</span><span class="mt"><i style="width:)\d+(%"></i></span><span class="mm">)\d+( 則 · )[0-9.]+(★</span>)',
            lambda m, idx=idx: (m.group(1) + str(s["q2_month_width"][idx]) + m.group(2)
                                + str(s["q2_month_count"][idx]) + m.group(3)
                                + _a2(s["q2_month_avg"][idx]) + m.group(4)),
            f"monthly {mo}月")
    return html


def _sync_trend_prose(html: str, s: dict) -> str:
    """評分趨勢關鍵洞察 — numbers embedded in the three insight sentences."""
    html = _subn(html,
                 r'(iOS )[+−][0-9.]+( ★、Android )[+−][0-9.]+( ★，Q2 雙平台 )[+−][0-9.]+( ★。)',
                 lambda m: (m.group(1) + _sign(s["brand_as_delta"][0]) + m.group(2) + _sign(s["brand_gp_delta"][0])
                            + m.group(3) + _sign(s["brand_delta"][0]) + m.group(4)),
                 "trend prose 元大")
    html = _subn(html,
                 r'(Q2 雙平台 )[+−][0-9.]+( ★，App Store 拉升至 )[0-9.]+(★，但 Google Play 從 )[0-9.]+(★ 回落至 )[0-9.]+(★；)',
                 lambda m: (m.group(1) + _sign(s["brand_delta"][1]) + m.group(2) + _a2(s["brand_as_q2_avg"][1])
                            + m.group(3) + _a2(s["brand_gp_q1_avg"][1]) + m.group(4) + _a2(s["brand_gp_q2_avg"][1]) + m.group(5)),
                 "trend prose 永豐")
    html = _subn(html, r'(國泰：Q2 急跌 )[+−][0-9.]+( ★，系統穩定)',
                 lambda m: m.group(1) + _sign(s["brand_delta"][2]) + m.group(2), "trend prose 國泰 title")
    html = _subn(html,
                 r'(Q2 雙平台 )[+−][0-9.]+( ★，Google Play 僅 )[0-9.]+(★、App Store )[0-9.]+(★。)',
                 lambda m: (m.group(1) + _sign(s["brand_delta"][2]) + m.group(2) + _a2(s["brand_gp_q2_avg"][2])
                            + m.group(3) + _a2(s["brand_as_q2_avg"][2]) + m.group(4)),
                 "trend prose 國泰 body")
    return html


def _sync_common_pain(html: str, s: dict) -> str:
    """三大券商共同痛點 — 6 月低分評論 per-brand counts (June, rating ≤ 2)."""
    return _subn(html, r'(6 月低分評論元大 )\d+( 則、永豐 )\d+( 則、國泰 )\d+( 則)',
                 lambda m: (m.group(1) + str(s["june_low"][0]) + m.group(2) + str(s["june_low"][1])
                            + m.group(3) + str(s["june_low"][2]) + m.group(4)),
                 "共同痛點 6月低分")


def _sync_modal(html: str, s: dict) -> str:
    """reviewDatabase modal title aggregate (國泰 dual delta; ASCII sign here)."""
    d = s["brand_delta"][2]
    return _subn(html, r"(國泰證券：Q2 急跌 )-?[0-9.]+( ★',)",
                 lambda m: m.group(1) + f"{'-' if d < 0 else '+'}{abs(d):.2f}" + m.group(2), "modal 國泰 delta")


def sync_web_dashboard() -> bool:
    """Refresh Yuanta_Reviews_Web.html in place. Returns True if the file changed."""
    reviews = web_data.load_reviews()
    stats = web_data.compute_stats(reviews)

    path = Path(config.BASE_DIR) / WEB_HTML
    original = path.read_text(encoding="utf-8")

    html = _sync_all_reviews(original, reviews)
    html = _sync_charts(html, stats)
    html = _sync_kpis(html, stats)
    html = _sync_brand_cards(html, stats)
    html = _sync_narrative_scores(html, stats)
    html = _sync_meta(html, stats)
    html = _sync_competitor(html, stats)
    html = _sync_tab2(html, stats)
    html = _sync_core_metrics(html, stats)
    html = _sync_monthly(html, stats)
    html = _sync_trend_prose(html, stats)
    html = _sync_common_pain(html, stats)
    html = _sync_modal(html, stats)

    if html != original:
        path.write_text(html, encoding="utf-8")
        logger.info(f"  🧭 已同步 Web 儀表板資料：{WEB_HTML}（總計 {stats['total']} 則）")
        return True
    logger.info(f"  🧭 Web 儀表板資料已是最新：{WEB_HTML}")
    return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sync_web_dashboard()
