"""
build_site.py — render the static dashboard from data.json.

Reads ../site/data.json (regenerating it via analyze.py if missing/--fresh) and
writes ../site/index.html — a self-contained page (data embedded inline so it
opens straight from disk, no server/CORS needed).
"""
from __future__ import annotations

import argparse
import json

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import ANALYSIS_DIR, SITE_DIR, DATA_JSON
import analyze


def build(fresh: bool = False) -> None:
    if fresh or not DATA_JSON.exists():
        analyze.main()
    data = json.loads(DATA_JSON.read_text(encoding="utf-8"))

    env = Environment(
        loader=FileSystemLoader(str(ANALYSIS_DIR / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    tmpl = env.get_template("index.html.j2")
    html = tmpl.render(
        data_json=json.dumps(data, ensure_ascii=False),
        generated_at=data["meta"]["generated_at"],
        model=data["meta"]["model"],
        quality=data["meta"]["quality"],
    )
    out = SITE_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out.relative_to(out.parents[1])} ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true", help="re-run analysis before rendering")
    build(**vars(ap.parse_args()))
