"""
insights.py — turn the analysed data into the narrative blocks the team reads:

  * rating-trend key insights (各家評分趨勢關鍵洞察)
  * Yuanta core pain points    (元大核心痛點詳析)
  * competitor deep-dive        (競品深度分析)
  * comparison × opportunities  (競品比較洞察 × 元大機會點)
  * 3-horizon strategy roadmap  (策略建議走向)

Everything here is derived from the model output (themes / intents / ratings),
so it refreshes automatically when the data changes. The only hand-authored part
is the action wording per theme (REC / HORIZON), which maps a data-found theme to
a concrete product recommendation.
"""
from __future__ import annotations

import numpy as np

from config import APP_BY_KEY, HERO_KEY

# Concrete product action per pain-point theme.
REC = {
    "登入與連線": "背景登入保活、生物辨識快速登入、弱網自動重連",
    "效能與穩定": "開盤尖峰壓測、行情推送與下單路徑優化、崩潰即時監控",
    "委託單功能": "補齊停損單／停利單／觸價單／條件單，並支援零股",
    "海外與複委託": "美股每檔成本與報酬率、股息再投入、複委託對帳",
    "庫存與損益": "庫存市值／成本／損益即時且正確、跨市場總資產總覽",
    "行情與技術分析": "技術線型除權息還原、EMA／均線、籌碼資料補完",
    "開戶與驗證": "線上開戶表單防呆、文件上傳穩定、身分驗證簡化",
    "介面與體驗": "簡化下單與庫存動線、漲跌紅綠標示、自選↔庫存快速切換",
    "定期定額與長期投資": "定期定額／存股明細、配息紀錄、長期報酬視圖",
    "交易成本與優惠": "手續費透明化、優惠與抽獎活動整合",
}

# Plain-language description of what each theme actually covers (the thing the
# matrix's one-word label can't convey on its own).
DESC = {
    "登入與連線": "頻繁被登出、重新登入、生物辨識失效，或一開 App 就卡在連線中——影響每天進場的第一步。",
    "效能與穩定": "開盤尖峰下單卡頓、報價或選擇權跳動消失、閃退與當機，直接造成下單延誤與虧損。",
    "委託單功能": "缺停損單／停利單／觸價單／條件單，零股與進階委託不足，逼用戶轉去別家下單。",
    "海外與複委託": "美股複委託缺每檔成本與報酬率、股息再投入，海外資產資訊不完整。",
    "庫存與損益": "庫存市值／成本／損益顯示錯誤或不即時，缺跨市場的總資產總覽。",
    "行情與技術分析": "技術線型除權息未還原、缺 EMA／均線、籌碼與法人資料不足。",
    "開戶與驗證": "線上開戶表單卡關、文件上傳失敗、切換 App 後已填資料被清空。",
    "介面與體驗": "改版後動線變亂、彈窗干擾交易、字體或圖表縮小、功能入口難找。",
    "定期定額與長期投資": "定期定額／存股明細與配息紀錄不足，缺長期報酬視圖。",
    "交易成本與優惠": "手續費不透明、優惠與抽獎活動分散難找。",
}

# Which delivery horizon each theme belongs to.
HORIZON = {
    "介面與體驗": "quick", "開戶與驗證": "quick", "庫存與損益": "quick",
    "登入與連線": "mid", "效能與穩定": "mid", "行情與技術分析": "mid",
    "委託單功能": "long", "海外與複委託": "long",
    "定期定額與長期投資": "long", "交易成本與優惠": "long",
}
HORIZON_META = {
    "quick": {"label": "體驗還原與流程防呆", "window": "1 個月內"},
    "mid":   {"label": "系統效能與數據穩定", "window": "3 個月內"},
    "long":  {"label": "功能超車與定位收割", "window": "6 個月內"},
}


def _rep_list(g, k=2, prefer_negative=True):
    """Top-k distinct, most on-topic reviews within a group (real user quotes)."""
    if prefer_negative:
        neg = g[(g["rating"] <= 2) | (g["intent"] == "complaint")]
    else:
        neg = g[g["rating"] >= 4]
    g = neg if len(neg) else g
    if not len(g):
        return []
    g = g.sort_values("theme_weight", ascending=False)
    out, seen = [], set()
    for _, r in g.iterrows():
        text = (r["text"] or "")[:170]
        key = text[:18]
        if not text or key in seen:
            continue
        seen.add(key)
        out.append({
            "rating": int(r["rating"]),
            "platform": r["platform"],
            "date": r["date"],
            "text": text,
        })
        if len(out) >= k:
            break
    return out


# --------------------------------------------------------------------------- #
def rating_trend(apps, order):
    cards = []
    slopes = {}
    for key in order:
        a = apps[key]
        pts = [m for m in sorted(a["monthly"], key=lambda x: x["month"]) if m["avg"] is not None]
        if len(pts) < 2:
            continue
        first, last = pts[0], pts[-1]
        delta = round(last["avg"] - first["avg"], 2)
        xs = np.arange(len(pts))
        slope = float(np.polyfit(xs, [p["avg"] for p in pts], 1)[0])
        slopes[key] = slope
        low = min(pts, key=lambda p: p["avg"])
        direction = "上升" if slope > 0.03 else ("下滑" if slope < -0.03 else "持平")
        cards.append({
            "key": key, "name": a["name"], "color": a["color"],
            "first_month": first["month"], "first_avg": first["avg"],
            "last_month": last["month"], "last_avg": last["avg"],
            "delta": delta, "direction": direction,
            "low_month": low["month"], "low_avg": low["avg"],
            "avg": a["avg_rating"],
            "text": (f"{first['month']}→{last['month']}：{first['avg']}★ → {last['avg']}★"
                     f"（{'+' if delta>=0 else ''}{delta}），整體{direction}；"
                     f"最低點 {low['month']}（{low['avg']}★）。"),
        })
    # overall summary
    best = max(apps.values(), key=lambda a: a["avg_rating"] or 0)
    hero = apps[HERO_KEY]
    hero_dir = next((c["direction"] for c in cards if c["key"] == HERO_KEY), "持平")
    summary = [
        f"{best['name']} 評分最高（{best['avg_rating']}★）且走勢最穩，是體驗標竿。",
        f"{hero['name']} 半年均分 {hero['avg_rating']}★，近半年趨勢{hero_dir}；"
        f"與標竿仍有 {round((best['avg_rating'] or 0) - (hero['avg_rating'] or 0), 2)}★ 差距。",
    ]
    return {"cards": cards, "summary": summary}


def _impact_line(share, neg, rank):
    sev = "高" if neg >= 0.7 else ("中高" if neg >= 0.55 else "中")
    head = "最該優先止血" if rank == 0 else ("需盡快處理" if rank <= 1 else "持續追蹤")
    return f"占自家評論 {share*100:.0f}%、負評率 {neg*100:.0f}%（嚴重度{sev}），{head}。"


def pain_points(df, app_key, top_n=4, with_narrative=False):
    assigned = df[(df["app"] == app_key) & (df["theme"] >= 0)]
    n_assigned = len(assigned)
    rows = []
    # group by LABEL so two NMF themes sharing a category merge into one card
    for label, g in assigned.groupby("theme_label"):
        if label not in REC:          # skip praise / non-actionable clusters
            continue
        complaints = int((g["intent"] == "complaint").sum())
        if complaints < 3:
            continue
        neg = float((g["rating"] <= 2).mean())
        rated = g[g["rating"] > 0]
        rows.append({
            "label": label,
            "n": int(len(g)), "complaints": complaints,
            "share": round(len(g) / n_assigned, 4) if n_assigned else 0.0,
            "avg": round(float(rated["rating"].mean()), 2) if len(rated) else None,
            "neg_share": round(neg, 4),
            "rec": REC[label],
            "_g": g,
            "severity": complaints * (0.5 + neg),
        })
    rows.sort(key=lambda r: r["severity"], reverse=True)
    rows = rows[:top_n]
    out = []
    for rank, r in enumerate(rows):
        g = r.pop("_g"); r.pop("severity", None)
        if with_narrative:
            r["desc"] = DESC.get(r["label"], "")
            r["quotes"] = _rep_list(g, k=2, prefer_negative=True)
            r["impact"] = _impact_line(r["share"], r["neg_share"], rank)
        out.append(r)
    return out


def _strength(df, app_key):
    """What this app is praised for: top praise-dominant theme + a 5★ quote."""
    assigned = df[(df["app"] == app_key) & (df["theme"] >= 0)]
    best = None
    for label, g in assigned.groupby("theme_label"):
        praise = int((g["intent"] == "praise").sum())
        if praise < 3:
            continue
        rated = g[g["rating"] > 0]
        avg = float(rated["rating"].mean()) if len(rated) else 0
        score = praise * avg
        if best is None or score > best["_score"]:
            best = {"label": label, "praise": praise,
                    "avg": round(avg, 2), "_score": score,
                    "quotes": _rep_list(g, k=1, prefer_negative=False)}
    if best:
        best.pop("_score", None)
    return best


def competitor_deep(df, apps, hero=HERO_KEY):
    """For each rival: their main pains + what they're praised for."""
    out = {}
    for key in apps:
        if key == hero:
            continue
        out[key] = {
            "name": apps[key]["name"],
            "vendor": apps[key]["vendor"],
            "color": apps[key]["color"],
            "avg": apps[key]["avg_rating"],
            "complaint_share": apps[key]["intents"]["complaint"]["share"],
            "praise_share": apps[key]["intents"]["praise"]["share"],
            "pains": pain_points(df, key, top_n=3, with_narrative=True),
            "strength": _strength(df, key),
        }
    return out


def shared_pains(theme_break, apps, hero=HERO_KEY, min_share=0.08):
    """Complaint themes where ALL three apps over-index — the industry-wide fights."""
    rows = []
    for t in theme_break:
        if t["dom_intent"] != "complaint" or t["label"] not in REC:
            continue
        shares = {k: t["by_app"][k]["share"] for k in apps}
        if min(shares.values()) < min_share:
            continue
        worst = max(shares, key=shares.get)
        rows.append({
            "label": t["label"],
            "desc": DESC.get(t["label"], ""),
            "shares": {k: round(v, 4) for k, v in shares.items()},
            "worst": worst, "worst_name": apps[worst]["name"],
            "hero_share": shares[hero],
        })
    rows.sort(key=lambda r: sum(r["shares"].values()), reverse=True)
    return rows[:3]


def learn_from(comp_deep):
    """Rival strengths Yuanta can learn from (from each rival's praise driver)."""
    out = []
    for key, d in comp_deep.items():
        s = d.get("strength")
        if not s:
            continue
        out.append({
            "rival_key": key, "rival_name": d["name"], "color": d["color"],
            "label": s["label"], "avg": s["avg"],
            "note": f"{d['name']} 好評率 {d['praise_share']*100:.0f}%，亮點在「{s['label']}」"
                    f"（該主題 {s['avg']}★）——元大可參考其做法。",
            "quote": s["quotes"][0] if s.get("quotes") else None,
        })
    out.sort(key=lambda x: x["avg"] or 0, reverse=True)
    return out


def opportunities(df, theme_break, gap, apps, hero=HERO_KEY):
    by_app = {t["id"]: t["by_app"] for t in theme_break}
    rivals = [k for k in APP_BY_KEY if k != hero]
    opps = []
    for grow in gap:
        label = grow["label"]
        if grow["gap"] <= 0.015 or label not in REC:
            continue
        if grow["dom_intent"] != "complaint":
            continue
        tid = grow["id"]
        rival = grow["best_rival"]
        hero_avg = by_app[tid][hero]["avg"]
        rival_avg = by_app[tid][rival]["avg"]
        opps.append({
            "id": tid, "label": label,
            "hero_share": grow["hero_share"], "hero_avg": hero_avg,
            "rival_key": rival, "rival_name": apps[rival]["name"],
            "rival_share": grow["best_rival_share"], "rival_avg": rival_avg,
            "gap": grow["gap"], "rec": REC[label],
            "insight": (f"「{label}」占元大評論 {grow['hero_share']*100:.0f}%，"
                        f"高出 {apps[rival]['name']} {grow['gap']*100:.0f} 個百分點"
                        + (f"；該主題元大 {hero_avg}★ vs {apps[rival]['name']} {rival_avg}★。"
                           if hero_avg and rival_avg else "。")),
        })
    return opps[:5]


def opportunities(df, theme_break, gap, apps, hero=HERO_KEY):
    by_app = {t["id"]: t["by_app"] for t in theme_break}
    rivals = [k for k in APP_BY_KEY if k != hero]
    opps = []
    for grow in gap:
        label = grow["label"]
        if grow["gap"] <= 0.015 or label not in REC:
            continue
        if grow["dom_intent"] != "complaint":
            continue
        tid = grow["id"]
        rival = grow["best_rival"]
        hero_avg = by_app[tid][hero]["avg"]
        rival_avg = by_app[tid][rival]["avg"]
        opps.append({
            "id": tid, "label": label,
            "hero_share": grow["hero_share"], "hero_avg": hero_avg,
            "rival_key": rival, "rival_name": apps[rival]["name"],
            "rival_share": grow["best_rival_share"], "rival_avg": rival_avg,
            "gap": grow["gap"], "rec": REC[label],
            "insight": (f"「{label}」占元大評論 {grow['hero_share']*100:.0f}%，"
                        f"高出 {apps[rival]['name']} {grow['gap']*100:.0f} 個百分點"
                        + (f"；該主題元大 {hero_avg}★ vs {apps[rival]['name']} {rival_avg}★。"
                           if hero_avg and rival_avg else "。")),
        })
    return opps[:5]


def roadmap(yuanta_pain, opps, max_per_horizon=2):
    """
    Bucket the actionable themes into the 3 horizons (quick/mid/long).

    Always emits all three stages so the strategic arc (止血 → 穩定 → 超車) stays
    intact; each stage keeps the strongest few themes (by pain order). Stages with
    no data-found theme fall back to a generic placeholder rather than vanishing.
    """
    order = {label: i for i, p in enumerate(yuanta_pain) for label in [p["label"]]}
    seen = {}
    for src in (yuanta_pain, opps):
        for item in src:
            label = item["label"]
            seen.setdefault(label, {"label": label, "rec": REC.get(label, ""),
                                    "rank": order.get(label, 99)})
    buckets = {"quick": [], "mid": [], "long": []}
    for item in seen.values():
        buckets[HORIZON.get(item["label"], "mid")].append(item)
    out = []
    for h in ("quick", "mid", "long"):
        items = sorted(buckets[h], key=lambda x: x["rank"])[:max_per_horizon]
        if not items:
            items = [{"label": HORIZON_META[h]["label"], "rec": "（本期資料未浮現明顯主題，持續觀察）"}]
        out.append({
            "horizon": h,
            "label": HORIZON_META[h]["label"],
            "window": HORIZON_META[h]["window"],
            "items": [{"label": it["label"], "rec": it["rec"]} for it in items],
        })
    return out


def build_insights(df, theme_break, gap, apps, order):
    # narrative blocks (each a distinct lens, written out with real quotes) —
    # this is what brings back the old version's at-a-glance clarity.
    yuanta_pain = pain_points(df, HERO_KEY, top_n=4, with_narrative=True)
    yuanta_pain_full = pain_points(df, HERO_KEY, top_n=8)   # seeds the roadmap
    comp_deep = competitor_deep(df, apps)
    opps = opportunities(df, theme_break, gap, apps)
    return {
        "rating_trend": rating_trend(apps, order),
        "yuanta_pain": yuanta_pain,
        "competitor_deep": comp_deep,
        "shared_pains": shared_pains(theme_break, apps),
        "learn_from": learn_from(comp_deep),
        "opportunities": opps,
        "roadmap": roadmap(yuanta_pain_full, opps),
    }
