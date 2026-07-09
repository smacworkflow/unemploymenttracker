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

    html = tpl.replace("__FRED_DATA__", json.dumps(data))
    os.makedirs(os.path.join(here, "_site"), exist_ok=True)
    with open(os.path.join(here, "_site", "index.html"), "w") as f:
        f.write(html)
    print(f"wrote _site/index.html ({len(html)/1024:.1f} KB), as-of {data['fetched_at']}")

if __name__ == "__main__":
    main()
