"""
config.py — paths and app metadata for the Reviews 2.0 analysis pipeline.

Everything downstream (parsing, theming, site build) imports from here so there
is a single source of truth for where data lives and how the three apps map to
their markdown files.
"""
from __future__ import annotations

from pathlib import Path

# analysis/ -> project root ("Yuanta App Reviews 2.0/")
ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = ROOT / "analysis"
SITE_DIR = ROOT / "site"           # generated output
DATA_JSON = SITE_DIR / "data.json"

STOPWORDS_FILE = ANALYSIS_DIR / "stopwords_zh.txt"
USERDICT_FILE = ANALYSIS_DIR / "userdict_zh.txt"

# --- The three apps under comparison -----------------------------------------
# key:   short id used internally / in the site
# name:  display name (zh)
# file_prefix: prefix for the quarterly JSON files in data/comments/
# color: brand-ish accent used in the dashboard
APPS = [
    {"key": "yuanta",  "name": "元大投資先生", "vendor": "元大證券",
     "file_prefix": "yuanta",  "color": "#e60012", "hero": True},
    {"key": "cathay",  "name": "國泰證券",     "vendor": "國泰證券",
     "file_prefix": "cathay",  "color": "#00a040", "hero": False},
    {"key": "sinopac", "name": "永豐金證券大戶", "vendor": "永豐金證券",
     "file_prefix": "sinopac", "color": "#f08300", "hero": False},
]

APP_BY_KEY = {a["key"]: a for a in APPS}
HERO_KEY = next(a["key"] for a in APPS if a.get("hero"))

# Number of themes to extract per app via NMF topic modelling.
N_THEMES = 8

# Intent labels for the complaint/request/praise classifier.
INTENT_LABELS = ["complaint", "request", "praise", "other"]
INTENT_ZH = {
    "complaint": "問題/抱怨",
    "request": "功能許願",
    "praise": "好評肯定",
    "other": "其他",
}
