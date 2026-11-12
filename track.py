#!/usr/bin/env python3
"""Log parking occupancy (parking.csv) and Wi-Fi client counts (wifi.csv) at Uni Ulm. Run from cron."""
import csv, datetime, json, pathlib, re, time, urllib.request

BASE = "http://tsu-app.rrooaarr.biz/front/"
HERE = pathlib.Path(__file__).parent
# Public Grafana dashboard of the uni network; panel 7 = eduroam clients, 9 = welcome clients.
GRAFANA = "https://grafana.uni-ulm.de/grafana/api/public/dashboards/c7d386879fae4b97b4dac792b7854d1d/panels/{}/query"
WIFI_PANELS = {"eduroam": 7, "welcome": 9}


def get(path):
    for attempt in (1, 2):  # the parking server sometimes drops out for a few seconds
        try:
            with urllib.request.urlopen(BASE + path, timeout=10) as r:
                return r.read().decode("utf-8", "replace")
        except OSError:
            if attempt == 2:
                raise
            time.sleep(5)


def append(name, header, rows):
    out = HERE / name
    new = not out.exists()
    with out.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerows(rows)


def wifi_clients(panel):
    # Without intervalMs Grafana answers in 30-min steps; 1-min steps make the last point "now".
    req = urllib.request.Request(GRAFANA.format(panel), data=b'{"intervalMs":60000,"maxDataPoints":1000}',
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return int(json.load(r)["results"]["A"]["frames"][0]["data"]["values"][1][-1])


# Lot list comes from the page itself, so new/renamed lots are picked up automatically.
# Parsed per <li> because some lots (P23) have no counter. M1/M2 share one counter.
lots = {}
try:
    page = get("mitarbeiter.html")
except OSError as e:
    # Still log Wi-Fi below. "::warning::" shows up as a yellow note on the GitHub run.
    print(f"::warning::parking site unreachable, no parking rows this run: {e}")
    page = ""
for li in page.split("<li")[1:]:
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
        # Despite the column name, the API returns *occupied* spaces; free = capacity - this.
        free = int(get(f"soap.php?counterid={cid}").strip())
    except (OSError, ValueError):
        free = ""  # keep the row so gaps are visible
    rows.append([now, cid, name, mx, free])

append("parking.csv", ["time", "counterid", "lot", "capacity", "free"], rows)

wifi = []
for net, panel in WIFI_PANELS.items():
    try:
        wifi.append(wifi_clients(panel))
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        wifi.append("")  # keep the row so gaps are visible
append("wifi.csv", ["time", *WIFI_PANELS], [[now, *wifi]])
