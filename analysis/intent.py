"""
intent.py — classify each review as complaint / request / praise / other.

There are no ground-truth labels, so we use **weak supervision**:
  1. derive high-confidence seed labels from the star rating + keyword lexicons,
  2. train a scikit-learn LogisticRegression on the TF-IDF of those seeds,
  3. let the model label *every* review — generalising past the keyword lists.

A stratified cross-val score on the seeds is printed so the bootstrap quality is
auditable.
"""
from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score

from text_zh import tokenize

_NEG = ["爛", "差", "閃退", "卡頓", "卡卡", "卡住", "當機", "延遲", "緩慢", "很慢",
        "無法", "不能", "沒辦法", "垃圾", "失望", "騙", "糟", "退步", "倒退", "故障",
        "錯誤", "被登出", "轉圈", "處理中", "不穩", "難用", "退錢", "跳出", "鳥",
        "問題", "怎麼辦", "客訴", "停損單都沒", "爛死"]
_REQ = ["希望", "建議", "可以增加", "增加", "新增", "可不可以", "能不能", "能否",
        "麻煩", "許願", "期待", "何時", "什麼時候", "拜託", "改善", "改進", "加入",
        "開放", "提供", "可否", "懇請", "求", "盼", "敬請", "是否可以", "是否能"]
_POS = ["好用", "讚", "推薦", "方便", "最棒", "喜歡", "感謝", "順暢", "很棒", "滿意",
        "快速", "清楚", "不錯", "好評", "給讚", "厲害", "強大", "完美", "流暢", "優秀",
        "簡單好", "愛用", "神器", "貼心"]


def _count(text: str, kws) -> int:
    return sum(text.count(k) for k in kws)


def _seed_label(text: str, rating: int) -> str | None:
    """High-confidence weak label, or None if too ambiguous to train on."""
    neg = _count(text, _NEG) + (2 if rating and rating <= 2 else 0)
    req = _count(text, _REQ)
    pos = _count(text, _POS) + (1 if rating and rating >= 4 else 0)

    scores = {"complaint": neg, "request": req, "praise": pos}
    top = max(scores, key=scores.get)
    if scores[top] == 0:
        return None  # no signal -> not a training seed; resolved later by the model
    # require a clear margin over the runner-up to be a trustworthy seed
    ordered = sorted(scores.values(), reverse=True)
    if ordered[0] - ordered[1] < 1:
        return None
    return top


# below this max-probability the model isn't confident -> label "other"
_OTHER_THRESHOLD = 0.45


def classify_intents(df, verbose: bool = False):
    """Adds an 'intent' column (predicted for all rows) and returns (df, report)."""
    df = df.copy()
    seeds = [
        _seed_label(t, r) for t, r in zip(df["text"].astype(str), df["rating"].fillna(0).astype(int))
    ]
    df["intent_seed"] = seeds

    # train only on the three real intents; "other" is assigned post-hoc by low
    # model confidence rather than learned from a handful of seeds.
    train = df[df["intent_seed"].isin(["complaint", "request", "praise"])]
    vec = TfidfVectorizer(tokenizer=tokenize, token_pattern=None, min_df=3, ngram_range=(1, 2))
    X_all = vec.fit_transform(df["text"].astype(str))
    X_train = vec.transform(train["text"].astype(str))
    y_train = train["intent_seed"].to_numpy()

    clf = LogisticRegression(max_iter=2000, class_weight="balanced", C=2.0)

    # auditable cross-val on the seeds
    cv = cross_val_score(clf, X_train, y_train, cv=5, scoring="f1_macro")
    clf.fit(X_train, y_train)

    proba = clf.predict_proba(X_all)
    top_idx = proba.argmax(axis=1)
    conf = proba.max(axis=1)
    pred = clf.classes_[top_idx]
    df["intent"] = np.where(conf >= _OTHER_THRESHOLD, pred, "other")
    df["intent_conf"] = conf.round(3)

    report = {
        "n_seeds": int(len(train)),
        "seed_dist": train["intent_seed"].value_counts().to_dict(),
        "cv_f1_macro": round(float(cv.mean()), 3),
        "cv_f1_std": round(float(cv.std()), 3),
        "pred_dist": df["intent"].value_counts().to_dict(),
    }
    if verbose:
        print(f"seeds: {report['n_seeds']}  seed_dist={report['seed_dist']}")
        print(f"5-fold F1(macro) on seeds: {report['cv_f1_macro']} ± {report['cv_f1_std']}")
        print(f"predicted dist (all {len(df)}): {report['pred_dist']}")
    return df, report


if __name__ == "__main__":
    from parse_reviews import load_all

    df = load_all()
    df, rep = classify_intents(df, verbose=True)
    print("\nBy app (predicted intent share):")
    print(
        df.groupby(["app_name", "intent"]).size()
        .groupby(level=0).apply(lambda s: (s / s.sum() * 100).round(1))
    )
