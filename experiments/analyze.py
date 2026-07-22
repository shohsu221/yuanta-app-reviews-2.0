"""
analyze.py — orchestrate parse -> themes -> intent -> aggregates -> data.json.

Produces the single JSON payload the static site renders from. Run directly:

    python analyze.py            # writes ../site/data.json
"""
from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd

from config import APPS, APP_BY_KEY, HERO_KEY, INTENT_LABELS, INTENT_ZH, DATA_JSON, SITE_DIR
from parse_reviews import load_all
from themes import fit_themes
from intent import classify_intents
from insights import build_insights


def _native(o):
    """Make numpy/pandas scalars JSON-serialisable."""
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(f"not serialisable: {type(o)}")


def _rating_dist(s: pd.Series) -> dict:
    counts = s[s > 0].value_counts()
    return {str(r): int(counts.get(r, 0)) for r in range(1, 6)}


def _per_app(df: pd.DataFrame, key: str) -> dict:
    a = APP_BY_KEY[key]
    sub = df[df["app"] == key]
    rated = sub[sub["rating"] > 0]
    n = int(len(sub))

    # platforms
    platforms = {}
    for plat, g in sub.groupby("platform"):
        gr = g[g["rating"] > 0]
        platforms[plat] = {
            "n": int(len(g)),
            "avg": round(float(gr["rating"].mean()), 2) if len(gr) else None,
        }

    # intents
    intent_counts = sub["intent"].value_counts()
    intents = {
        lab: {
            "n": int(intent_counts.get(lab, 0)),
            "share": round(float(intent_counts.get(lab, 0)) / n, 4) if n else 0.0,
        }
        for lab in INTENT_LABELS
    }

    # monthly trend
    monthly = []
    for month, g in sub[sub["month"].notna()].groupby("month"):
        gr = g[g["rating"] > 0]
        monthly.append({
            "month": month,
            "n": int(len(g)),
            "avg": round(float(gr["rating"].mean()), 2) if len(gr) else None,
            "complaint": int((g["intent"] == "complaint").sum()),
        })
    monthly.sort(key=lambda d: d["month"])

    # versions (skip unknown), keep those with >=4 reviews, order by recency
    versions = []
    known = sub[(sub["version"].notna()) & (sub["version"] != "未知") & (sub["version"] != "")]
    for ver, g in known.groupby("version"):
        gr = g[g["rating"] > 0]
        versions.append({
            "version": ver,
            "n": int(len(g)),
            "avg": round(float(gr["rating"].mean()), 2) if len(gr) else None,
            "last": g["date"].dropna().max(),
        })
    versions = [v for v in versions if v["n"] >= 4]
    versions.sort(key=lambda d: (d["last"] or ""))

    return {
        "key": key,
        "name": a["name"],
        "vendor": a["vendor"],
        "color": a["color"],
        "hero": a.get("hero", False),
        "n": n,
        "avg_rating": round(float(rated["rating"].mean()), 2) if len(rated) else None,
        "rating_dist": _rating_dist(sub["rating"]),
        "platforms": platforms,
        "intents": intents,
        "monthly": monthly,
        "versions": versions,
    }


def _theme_breakdown(df: pd.DataFrame, themes_meta: list) -> list:
    """
    Per-theme competitive breakdown, grouped by *label* so two NMF components
    that map to the same category (e.g. two 效能與穩定 themes) merge into ONE
    row — no duplicate-looking entries in the matrix.
    """
    assigned = df[df["theme"] >= 0]
    app_totals = assigned.groupby("app").size().to_dict()

    # collect the constituent NMF top-terms for each label
    terms_by_label: dict[str, list] = {}
    for m in themes_meta:
        terms_by_label.setdefault(m["label"], []).extend(m["top_terms"])

    out = []
    for label, members in assigned.groupby("theme_label"):
        by_app = {}
        for key in APP_BY_KEY:
            am = members[members["app"] == key]
            tot = app_totals.get(key, 0)
            by_app[key] = {
                "n": int(len(am)),
                "share": round(len(am) / tot, 4) if tot else 0.0,
                "avg": round(float(am[am["rating"] > 0]["rating"].mean()), 2) if (am["rating"] > 0).any() else None,
            }
        neg = int((members["rating"] <= 2).sum())
        dom_intent = members["intent"].value_counts().idxmax() if len(members) else "other"
        terms = list(dict.fromkeys(terms_by_label.get(label, [])))[:8]
        out.append({
            "id": label,                       # label is the stable key
            "label": label,
            "top_terms": terms,
            "size": int(len(members)),
            "share": round(len(members) / len(assigned), 4) if len(assigned) else 0.0,
            "by_app": by_app,
            "neg_share": round(neg / len(members), 4) if len(members) else 0.0,
            "dom_intent": dom_intent,
            "dom_intent_zh": INTENT_ZH.get(dom_intent, dom_intent),
        })
    out.sort(key=lambda d: d["size"], reverse=True)
    return out


def _competitor_gap(theme_break: list, hero: str = HERO_KEY) -> list:
    """
    Where does the hero app (Yuanta) over-index on a theme vs its best rival?
    gap = hero_share - min(rival_share). Positive => Yuanta has proportionally
    MORE of this theme than the best competitor (bad for complaint themes).
    """
    rivals = [k for k in APP_BY_KEY if k != hero]
    rows = []
    for t in theme_break:
        hero_share = t["by_app"][hero]["share"]
        rival_shares = {r: t["by_app"][r]["share"] for r in rivals}
        best_rival = min(rival_shares, key=rival_shares.get)
        gap = round(hero_share - rival_shares[best_rival], 4)
        rows.append({
            "id": t["id"],
            "label": t["label"],
            "dom_intent": t["dom_intent"],
            "hero_share": hero_share,
            "hero_avg": t["by_app"][hero]["avg"],
            "rival_shares": rival_shares,
            "best_rival": best_rival,
            "best_rival_share": rival_shares[best_rival],
            "gap": gap,
        })
    rows.sort(key=lambda d: d["gap"], reverse=True)
    return rows


def _headlines(apps: dict, gap: list, insights: dict, hero: str = HERO_KEY) -> list:
    """Three decision-oriented takeaways (the 'so what', not a number recap)."""
    h = apps[hero]
    best = max(apps.values(), key=lambda a: a["avg_rating"] or 0)
    behind = round((best["avg_rating"] or 0) - (h["avg_rating"] or 0), 2)
    trend = next((c for c in insights["rating_trend"]["cards"] if c["key"] == hero), {})
    direction = trend.get("direction", "持平")

    lines = []
    # 1) competitive position + momentum -> implication
    lines.append(
        f"競爭定位：{h['name']} 落後體驗標竿 {best['name']} {behind}★，"
        f"且近半年趨勢{direction}——體驗負債正在{'擴大' if direction=='下滑' else '累積'}，需要止血。"
    )
    # 2) the single biggest competitive loss
    worst = gap[0] if gap and gap[0]["gap"] > 0 else None
    if worst:
        lines.append(
            f"最大失分點：「{worst['label']}」的抱怨在 {h['name']} 占比高出最佳對手 "
            f"{apps[worst['best_rival']]['name']} {worst['gap']*100:.0f} 個百分點，是被拉開差距的主因。"
        )
    # 3) where to aim, from the intent mix
    comp = h["intents"]["complaint"]["share"]
    req = h["intents"]["request"]["share"]
    lines.append(
        f"行動順序：{comp*100:.0f}% 的評論是抱怨、只有 {req*100:.0f}% 是功能許願——"
        f"先把穩定度與登入體驗止血，再談功能超車。"
    )
    return lines


def run_analysis() -> dict:
    df = load_all()
    quality_stats = {
        "n_raw": int(df.attrs.get("n_raw", len(df))),
        "n_kept": int(df.attrs.get("n_kept", len(df))),
        "n_dropped": int(df.attrs.get("n_dropped", 0)),
    }
    df, themes_meta = fit_themes(df)
    # map each review's NMF theme id to its human label so everything downstream
    # can group by the merged category rather than the raw component id.
    id2label = {m["id"]: m["label"] for m in themes_meta}
    df["theme_label"] = df["theme"].map(lambda i: id2label.get(int(i)) if i >= 0 else None)
    df, intent_report = classify_intents(df)

    apps = {key: _per_app(df, key) for key in APP_BY_KEY}
    theme_break = _theme_breakdown(df, themes_meta)
    gap = _competitor_gap(theme_break)
    insights = build_insights(df, theme_break, gap, apps, [a["key"] for a in APPS])
    headlines = _headlines(apps, gap, insights)

    # a few representative reviews per theme (by label) for the drill-down panel
    assigned = df[df["theme"] >= 0]
    examples = {}
    for t in theme_break:
        mem = assigned[assigned["theme_label"] == t["id"]].sort_values("theme_weight", ascending=False)
        examples[str(t["id"])] = [
            {
                "app": r["app"],
                "rating": int(r["rating"]),
                "intent": r["intent"],
                "date": r["date"],
                "text": (r["text"] or "")[:160],
            }
            for _, r in mem.head(6).iterrows()
        ]

    return {
        "meta": {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "n_reviews": int(len(df)),
            "quality": quality_stats,
            "hero": HERO_KEY,
            "apps_order": [a["key"] for a in APPS],
            "intent_labels": INTENT_LABELS,
            "intent_zh": INTENT_ZH,
            "model": {
                "themes": "TF-IDF + NMF (scikit-learn)",
                "intent": "TF-IDF + LogisticRegression, weak-supervised",
                "intent_cv_f1_macro": intent_report["cv_f1_macro"],
                "intent_seeds": intent_report["n_seeds"],
                "tokenizer": "jieba + domain user-dict",
            },
        },
        "apps": apps,
        "themes": theme_break,
        "competitor_gap": gap,
        "headlines": headlines,
        "insights": insights,
        "examples": examples,
    }


def main():
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    payload = run_analysis()
    DATA_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_native), encoding="utf-8")
    print(f"wrote {DATA_JSON.relative_to(DATA_JSON.parents[1])} "
          f"({len(json.dumps(payload, default=_native))/1024:.0f} KB)")
    print("headlines:")
    for h in payload["headlines"]:
        print("  -", h)


if __name__ == "__main__":
    main()
