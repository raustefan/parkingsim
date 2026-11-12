#!/usr/bin/env python3
"""Log parking, network, lecture, weather and transit data at Uni Ulm to one CSV per source. Run from cron."""
import csv, datetime, html, json, pathlib, re, time, urllib.request, zoneinfo

HERE = pathlib.Path(__file__).parent
PARKING = "http://tsu-app.rrooaarr.biz/front/"
# Public Grafana dashboard of the uni network (kiz). Each CSV gets one column per panel.
GRAFANA = "https://grafana.uni-ulm.de/grafana/api/public/dashboards/c7d386879fae4b97b4dac792b7854d1d/panels/{}/query"
GRAFANA_CSVS = {
    "wifi.csv": {"eduroam": 7, "welcome": 9},  # connected devices
    "traffic.csv": {"eduroam_bps": 22, "welcome_bps": 46, "uplink_stg_bps": 47, "uplink_ka_bps": 52},  # bits/s
    "firewall.csv": {"kizbox01": 60, "kizbox02": 61},  # clients behind the kiz firewalls
}
LSF = ("https://campusonline.uni-ulm.de/qislsf/rds?state=currentLectures&type={}&next=CurrentLectures.vm"
       "&nextdir=ressourcenManager&topitem=lectures&asi=")  # type 0 = today's events, 1 = cancelled today
WEATHER = ("https://api.open-meteo.com/v1/forecast?latitude=48.4225&longitude=9.95&timezone=Europe%2FBerlin"
           "&current=temperature_2m,precipitation,cloud_cover,wind_speed_10m,weather_code")
DING = ("https://www.ding.eu/ding3/XML_DM_REQUEST?outputFormat=JSON&type_dm=stop&mode=direct&limit=40&useRealtime=1"
        "&name_dm=Ulm%20Universit%C3%A4t%20S%C3%BCd")

# Berlin local time with UTC offset: keeps "hour of day" right across DST switches, and stays unambiguous
# for the repeated hour in October. Every CSV row of one run shares this timestamp, so files join on `time`.
NOW = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Berlin")).replace(microsecond=0)
now = NOW.isoformat()


def fetch(url, data=None, timeout=15):
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    for attempt in (1, 2):  # servers sometimes drop out for a few seconds
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
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


def log(name, columns, read):
    """Append one row [now, *read()] to name. If read fails, log an empty row so the gap is visible."""
    try:
        values = read()
    except Exception as e:  # one broken source must never stop the others
        # "::warning::" shows up as a yellow note on the GitHub run.
        print(f"::warning::{name}: {e!r}")
        values = [""] * len(columns)
    append(name, ["time", *columns], [[now, *values]])


def parking():
    # Lot list comes from the page itself, so new/renamed lots are picked up automatically.
    # Parsed per <li> because some lots (P23) have no counter. M1/M2 share one counter.
    try:
        page = fetch(PARKING + "mitarbeiter.html", timeout=10)
    except OSError as e:
        print(f"::warning::parking site unreachable, no parking rows this run: {e}")
        return
    lots = {}
    for li in page.split("<li")[1:]:
        m = re.search(r'p-number">\s*([^<]+?)\s*<.*?cid="(\d+)" max="(\d+)"', li, re.S)
        if m:
            name, cid, mx = m.groups()
            lots.setdefault(cid, (name, mx))
    rows = []
    for cid, (name, mx) in lots.items():
        try:
            # Despite the column name, the API returns *occupied* spaces; free = capacity - this.
            free = int(fetch(f"{PARKING}soap.php?counterid={cid}", timeout=10).strip())
        except (OSError, ValueError):
            free = ""  # keep the row so gaps are visible
        rows.append([now, cid, name, mx, free])
    append("parking.csv", ["time", "counterid", "lot", "capacity", "free"], rows)


def grafana(panel):
    # Without intervalMs Grafana answers in 30-min steps; 1-min steps make the last point "now".
    frame = json.loads(fetch(GRAFANA.format(panel), data=b'{"intervalMs":60000,"maxDataPoints":1000}'))
    values = frame["results"]["A"]["frames"][0]["data"]["values"][1]
    return round(next(v for v in reversed(values) if v is not None))


def lsf_events(kind):
    """Rows (begin, end, number, title, building, room) from the public 'today' list of the course catalogue."""
    page = fetch(LSF.format(kind), timeout=30)
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>|\s+", " ", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) >= 6 and re.fullmatch(r"\d\d:\d\d", cells[0]):
            rows.append(cells[:6])
    return rows


def lectures():
    hhmm = NOW.strftime("%H:%M")
    running = [r for r in lsf_events(0) if r[0] <= hhmm < r[1]]  # "24:00" still sorts after any real time
    courses = [r for r in running if r[2]]  # entries with a course number are real courses, not room blocks
    rooms = {(r[4], r[5]) for r in running if r[5]}
    return [len(running), len(courses), len(rooms), len(lsf_events(1))]


def weather():
    c = json.loads(fetch(WEATHER))["current"]
    return [c["temperature_2m"], c["precipitation"], c["cloud_cover"], c["wind_speed_10m"], c["weather_code"]]


def transit():
    soon = [d for d in json.loads(fetch(DING, timeout=20))["departureList"] or [] if int(d["countdown"]) <= 30]
    delays = [int(d["servingLine"]["delay"]) for d in soon if d["servingLine"].get("delay") is not None]
    return [len(soon), len(delays), round(sum(delays) / len(delays), 2) if delays else "", max(delays, default="")]


parking()
for name, panels in GRAFANA_CSVS.items():
    log(name, list(panels), lambda panels=panels: [grafana(p) for p in panels.values()])
log("lectures.csv", ["events_now", "courses_now", "rooms_in_use", "cancelled_today"], lectures)
log("weather.csv", ["temperature_c", "precipitation_mm", "cloud_cover_pct", "wind_kmh", "weather_code"], weather)
log("transit.csv", ["departures_30min", "realtime_30min", "avg_delay_min", "max_delay_min"], transit)
