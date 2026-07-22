"""
validate_dashboard.py — verify that the numbers baked into Yuanta_Reviews_Web.html
match the review Markdown data.

Runs after web_sync.sync_web_dashboard(); it is the guard that stops a stale or
mis-synced dashboard from being deployed. All expected values come from
web_data.compute_stats(), the same computation web_sync writes with.
"""
import ast
import re
from pathlib import Path

from crawler.utils import config
from crawler.sync import web_data

WEB_HTML = web_data.WEB_HTML


def _chart_arrays(html: str, chart_id: str) -> list:
    """Numeric `data:[...]` arrays inside one chart's `new Chart(...)` block."""
    start = html.index(f"getElementById('{chart_id}')")
    nxt = html.find("new Chart(", start + 1)
    end = nxt if nxt != -1 else len(html)
    section = html[start:end]
    return [ast.literal_eval(v) for v in re.findall(r"data:\s*(\[[0-9.,\s]+\])", section)]


def validate_dashboard(html_name: str = WEB_HTML) -> None:
    html = (Path(config.BASE_DIR) / html_name).read_text(encoding="utf-8")
    s = web_data.compute_stats()
    errors: list[str] = []

    # ── Chart datasets ──────────────────────────────────────────────
    star = _chart_arrays(html, "yuantaStarChart")
    if star[:2] != [s["yuanta_star_q1"], s["yuanta_star_q2"]]:
        errors.append(
            f"yuantaStarChart {star[:2]} != {[s['yuanta_star_q1'], s['yuanta_star_q2']]}"
        )

    brand = _chart_arrays(html, "brandCompareChart")
    if brand[:2] != [s["brand_q1_avg"], s["brand_q2_avg"]]:
        errors.append(
            f"brandCompareChart {brand[:2]} != {[s['brand_q1_avg'], s['brand_q2_avg']]}"
        )

    donut = _chart_arrays(html, "donutChart")
    if not donut or donut[0] != s["yuanta_donut"]:
        errors.append(f"donutChart {donut[:1]} != {s['yuanta_donut']}")

    # ── Headline KPIs ───────────────────────────────────────────────
    kpi_needles = [
        (f'<div class="mn">{s["total"]}</div><div class="ml">總評論</div>', "總評論"),
        (f'<div class="mn">{s["q2_avg"]:.2f}</div><div class="ml">Q2 均分</div>', "Q2 均分"),
        (f'{s["q2_low_pct"]}%</div><div class="ml">Q2 低分率</div>', "Q2 低分率"),
    ]
    for needle, label in kpi_needles:
        if needle not in html:
            errors.append(f"KPI {label} not current (expected {needle!r})")

    # ── Brand card scores (Q2 average) ──────────────────────────────
    for i, (_, _, css) in enumerate(web_data.BRANDS):
        needle = f'<span class="s">{s["brand_q2_avg"][i]:.2f}</span>'
        if needle not in html:
            errors.append(f"brand card {css} score not current ({s['brand_q2_avg'][i]:.2f})")

    if errors:
        raise ValueError(
            f"Dashboard validation failed ({html_name}): " + " | ".join(errors)
        )


if __name__ == "__main__":
    validate_dashboard()
    print("Dashboard validation passed.")
