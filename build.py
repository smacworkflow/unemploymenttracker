#!/usr/bin/env python3
"""Fetch FRED labor-market series and build _site/index.html from dashboard_template.html.

Runs on a GitHub Actions runner (open internet), so it uses FRED's CSV download
endpoint directly -- no API key required. Standard library only.
"""
import json, os, sys, urllib.request, datetime

SERIES = {
    "UNRATE":      ("U-3 unemployment rate", "monthly", "percent"),
    "U6RATE":      ("U-6 underemployment rate", "monthly", "percent"),
    "ICSA":        ("Initial jobless claims", "weekly", "number"),
    "CCSA":        ("Continuing jobless claims", "weekly", "number"),
    "JTSHIR":      ("Hires rate", "monthly", "percent"),
    "JTSQUR":      ("Quits rate", "monthly", "percent"),
    "JTSLDR":      ("Layoffs & discharges rate", "monthly", "percent"),
    "JTSTSR":      ("Total separations rate", "monthly", "percent"),
    "JTSJOL":      ("Job openings level (thousands)", "monthly", "number"),
    "UNEMPLOY":    ("Unemployed level (thousands)", "monthly", "number"),
    "UEMPMED":     ("Median duration of unemployment (weeks)", "monthly", "number"),
    "LNS13025703": ("Percent unemployed 27 weeks & over", "monthly", "percent"),
    "LNS12300060": ("Prime-age (25-54) employment-population ratio", "monthly", "percent"),
    "LNS11300060": ("Prime-age (25-54) labor force participation rate", "monthly", "percent"),
}
START = "2015-01-01"
UA = "Mozilla/5.0 (compatible; unemployment-tracker/1.0; +https://github.com)"

def fetch_csv(series_id):
    url = ("https://fred.stlouisfed.org/graph/fredgraph.csv"
           f"?id={series_id}&cosd={START}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8", "replace")
    obs = []
    for i, line in enumerate(text.splitlines()):
        if i == 0 or not line.strip():
            continue  # header
        parts = line.split(",")
        if len(parts) < 2:
            continue
        date, val = parts[0].strip(), parts[1].strip()
        if val in ("", "."):
            continue  # missing
        try:
            obs.append([date, float(val)])
        except ValueError:
            continue
    return obs


ARCHIVE_TPL = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Update notes — Structural Unemployment Tracker</title>
<style>
:root{color-scheme:light;--bg:#f7f7f5;--card:#ffffff;--ink:#1a1a17;--muted:#6b6b63;--line:#e4e3dd;--accent:#2f6f4f;--warn:#b4441f;--neutral:#8a8a80;--blue:#2b5c8a;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;font-size:14px;line-height:1.5;}
.wrap{max-width:780px;margin:0 auto;padding:24px 20px 60px;}
h1{font-size:22px;margin:0 0 4px;letter-spacing:-.01em;}
.sub{color:var(--muted);font-size:13px;margin:0 0 20px;}
.sub a{color:var(--blue);text-decoration:none;}
.entry{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:10px;padding:16px 18px;margin-bottom:16px;font-size:13.5px;}
.entry .meta{font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--accent);}
.entry h2{font-size:15px;margin:4px 0 8px;letter-spacing:-.01em;}
.entry .srcs{color:var(--muted);font-size:11.5px;margin-bottom:0;}
.vchip{display:inline-block;padding:1px 8px;border-radius:20px;font-size:10.5px;font-weight:600;margin-left:8px;vertical-align:1px;}
.vchip.more{background:#e8f1ec;color:var(--accent);}
.vchip.less{background:#f6e7e1;color:var(--warn);}
.vchip.mixed{background:#efefea;color:var(--neutral);}
</style></head><body><div class="wrap">
<h1>Update notes</h1>
<p class="sub">Commentary published after each full turn of the data set (keyed to the JOLTS release, the slowest series). <a href="index.html">&larr; Back to the tracker</a></p>
__ENTRIES__
</div></body></html>"""

VCHIP_LABELS = {"more": "thesis more validated", "less": "thesis less validated", "mixed": "mixed"}

def load_commentary(here):
    path = os.path.join(here, "commentary.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        notes = json.load(f)
    notes.sort(key=lambda n: n.get("ref_month", ""), reverse=True)
    return notes

def build_archive(here, notes):
    entries = []
    for n in notes:
        chip = ""
        v = n.get("verdict")
        if v:
            chip = f'<span class="vchip {v}">{VCHIP_LABELS.get(v, v)}</span>'
        entries.append(
            f'<div class="entry"><span class="meta">{n.get("ref_label", n.get("ref_month", ""))} data \u00b7 published {n.get("published", "")}</span>{chip}'
            f'<h2>{n.get("title", "")}</h2><div>{n.get("html", "")}</div></div>'
        )
    page = ARCHIVE_TPL.replace("__ENTRIES__", "\n".join(entries) or "<p>No notes yet.</p>")
    with open(os.path.join(here, "_site", "archive.html"), "w") as f:
        f.write(page)
    print(f"wrote _site/archive.html ({len(notes)} notes)")

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    tpl = open(os.path.join(here, "dashboard_template.html")).read()
    if "__FRED_DATA__" not in tpl:
        sys.exit("template missing __FRED_DATA__ placeholder")

    data = {"fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "series": {}}
    for sid, (label, freq, units) in SERIES.items():
        try:
            obs = fetch_csv(sid)
        except Exception as e:
            print(f"WARN {sid}: {e}", file=sys.stderr)
            obs = []
        # trim numbers to ints where whole (keeps file small; JS handles either)
        clean = [[d, (int(v) if float(v).is_integer() else round(v, 4))] for d, v in obs]
        data["series"][sid] = {"label": label, "freq": freq, "units": units, "obs": clean}
        print(f"{sid}: {len(clean)} obs" + (f", latest {clean[-1]}" if clean else ""))

    notes = load_commentary(here)
    html = tpl.replace("__FRED_DATA__", json.dumps(data))
    if "__COMMENTARY__" in html:
        html = html.replace("__COMMENTARY__", json.dumps(notes))
    os.makedirs(os.path.join(here, "_site"), exist_ok=True)
    with open(os.path.join(here, "_site", "index.html"), "w") as f:
        f.write(html)
    print(f"wrote _site/index.html ({len(html)/1024:.1f} KB), as-of {data['fetched_at']}")
    build_archive(here, notes)

if __name__ == "__main__":
    main()
