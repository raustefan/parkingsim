#!/usr/bin/env python3
"""Log free parking spaces at Uni Ulm to parking.csv. Run from cron."""
import csv, datetime, pathlib, re, urllib.request

BASE = "http://tsu-app.rrooaarr.biz/front/"
OUT = pathlib.Path(__file__).with_name("parking.csv")


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return r.read().decode("utf-8", "replace")


# Lot list comes from the page itself, so new/renamed lots are picked up automatically.
# Parsed per <li> because some lots (P23) have no counter. M1/M2 share one counter.
lots = {}
for li in get("mitarbeiter.html").split("<li")[1:]:
    m = re.search(r'p-number">\s*([^<]+?)\s*<.*?cid="(\d+)" max="(\d+)"', li, re.S)
    if m:
        name, cid, mx = m.groups()
        lots.setdefault(cid, (name, mx))

# Local time with UTC offset: keeps "hour of day" right across DST switches, and stays unambiguous
# for the repeated hour in October.
now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
rows = []
for cid, (name, mx) in lots.items():
    try:
        free = int(get(f"soap.php?counterid={cid}").strip())
    except (OSError, ValueError):
        free = ""  # keep the row so gaps are visible
    rows.append([now, cid, name, mx, free])

new = not OUT.exists()
with OUT.open("a", newline="") as f:
    w = csv.writer(f)
    if new:
        w.writerow(["time", "counterid", "lot", "capacity", "free"])
    w.writerows(rows)
