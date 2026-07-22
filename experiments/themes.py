"""
themes.py — data-driven theme extraction with TF-IDF + NMF (scikit-learn).

Strategy: fit ONE model on the combined 3-app corpus so every app is scored on
the *same* theme axis — that's what makes the competitor-gap view meaningful.
Each NMF component is given a human-readable category label by matching its top
terms against a small pain-point keyword map (falls back to the raw top terms).
"""
from __future__ import annotations

import numpy as np
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

from config import N_THEMES
from text_zh import tokenize

# Map a readable category onto a theme from signal terms in its top-terms list.
# Order matters: first match wins.
_LABEL_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("登入與連線", ("登入", "登出", "被登出", "重新登入", "啟動", "重新", "重開", "指紋", "人臉", "憑證", "連線", "連不上")),
    ("效能與穩定", ("閃退", "卡頓", "卡卡", "轉圈圈", "延遲", "當機", "處理", "lag", "緩慢", "停住", "更新")),
    ("委託單功能", ("停損單", "停利單", "觸價單", "條件單", "智慧單", "下單", "掛單", "委託")),
    ("海外與複委託", ("複委託", "美股", "海外", "港股", "股息再投入")),
    ("庫存與損益", ("庫存", "損益", "報酬率", "成本", "市值", "均價", "對帳", "資產")),
    ("行情與技術分析", ("k線", "均線", "技術分析", "線型", "報價", "走勢", "江波圖", "籌碼", "外資", "投信")),
    ("開戶與驗證", ("開戶", "驗證", "身分", "上傳", "註冊", "客服", "回覆")),
    ("介面與體驗", ("介面", "版面", "操作", "設計", "字體", "畫面", "改版", "ui", "體驗")),
    ("定期定額與長期投資", ("定期定額", "定期定股", "配息", "存股", "零股")),
    ("交易成本與優惠", ("手續費", "折扣", "優惠", "抽獎", "活動", "利息")),
]


def _label_for(top_terms: list[str]) -> str:
    """
    Rank-weighted labelling: a category scores higher when its keywords appear
    nearer the top of the theme's term list. Requires a reasonably strong match
    (a keyword within the top ~4 terms) before accepting a category label,
    otherwise falls back to the raw top terms (e.g. diffuse praise clusters).
    """
    # position weight: top term = len, next = len-1, ...
    weights = {t.lower(): len(top_terms) - i for i, t in enumerate(top_terms)}
    best_label, best_score = None, 0
    for label, keys in _LABEL_RULES:
        score = sum(weights.get(k, 0) for k in keys)
        if score > best_score:
            best_label, best_score = label, score
    # accept only if the signal is strong enough (>= a top-4 hit)
    if best_label and best_score >= len(top_terms) - 3:
        return best_label
    return "・".join(top_terms[:2]) if top_terms else "其他"


def fit_themes(df, n_themes: int = N_THEMES, random_state: int = 42):
    """
    Returns (df_with_theme, themes_meta).

    df_with_theme adds:
        theme        -> theme id (int) or -1 if the review had no usable tokens
        theme_weight -> NMF activation of the dominant theme
    themes_meta is a list of dicts: id, label, top_terms, size, share, example.
    """
    texts = df["text"].astype(str).tolist()

    vec = TfidfVectorizer(
        tokenizer=tokenize,
        token_pattern=None,
        min_df=4,
        max_df=0.5,
        ngram_range=(1, 1),
        sublinear_tf=True,
    )
    X = vec.fit_transform(texts)
    terms = np.array(vec.get_feature_names_out())

    nmf = NMF(
        n_components=n_themes,
        init="nndsvda",
        random_state=random_state,
        max_iter=600,
        beta_loss="frobenius",
    )
    W = nmf.fit_transform(X)        # docs x themes
    H = nmf.components_             # themes x terms

    # dominant theme per doc; mark docs with no signal as -1
    doc_sum = W.sum(axis=1)
    dominant = W.argmax(axis=1)
    dominant = np.where(doc_sum > 1e-9, dominant, -1)
    dom_weight = W.max(axis=1)

    df = df.copy()
    df["theme"] = dominant
    df["theme_weight"] = dom_weight

    # build metadata
    themes_meta = []
    n_assigned = int((dominant >= 0).sum())
    for t in range(n_themes):
        top_idx = H[t].argsort()[::-1][:12]
        top_terms = [terms[i] for i in top_idx]
        members = df[df["theme"] == t]
        size = int(len(members))
        # representative review = highest theme_weight in this theme, prefer longer text
        example = ""
        if size:
            rep = members.sort_values("theme_weight", ascending=False).iloc[0]
            example = (rep["text"] or "")[:140]
        themes_meta.append({
            "id": t,
            "label": _label_for(top_terms),
            "top_terms": top_terms[:8],
            "size": size,
            "share": round(size / n_assigned, 4) if n_assigned else 0.0,
            "example": example,
        })

    themes_meta.sort(key=lambda d: d["size"], reverse=True)
    return df, themes_meta


if __name__ == "__main__":
    from parse_reviews import load_all

    df = load_all()
    df, meta = fit_themes(df)
    assigned = (df["theme"] >= 0).sum()
    print(f"{len(df)} reviews, {assigned} assigned to a theme\n")
    for m in meta:
        print(f"[{m['id']}] {m['label']}  (n={m['size']}, {m['share']*100:.1f}%)")
        print("    terms:", " / ".join(m["top_terms"]))
        print("    e.g. :", m["example"][:80])
