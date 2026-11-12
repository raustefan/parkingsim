<img src="assets/icon.svg" width="64" height="64" alt="">

# parkingsim

Tracks parking lot occupancy at Ulm University every 5 minutes, together with context that explains it: campus Wi-Fi usage, network traffic, lectures running, weather and tram/bus delays. The goal is a model that predicts how full the lots are by time and weekday.

**Live site:** https://raustefan.github.io/parkingsim/

## How it works

- `track.py` fetches the current values and appends them to one CSV file per source. It only needs Python 3, no packages. If one source fails, the others are still logged and the GitHub run shows a yellow warning.
- `.github/workflows/track.yml` runs `track.py` and commits the CSVs. It's started every 5 minutes by a [cron-job.org](https://cron-job.org) job calling GitHub's `workflow_dispatch` API, because GitHub's own `schedule` trigger never fired for this repo.
- `site/index.html` is the GitHub Pages site (deployed by `.github/workflows/pages.yml` when `site/` changes). It reads the CSVs live from the repo, so new data shows up without redeploying.

## Data

Timestamps are Berlin local time with UTC offset (e.g. `2026-11-12T19:25:25+01:00`). An empty value means that reading failed.

**`parking.csv`**: one row per lot per run, from the [T.S.U. parking app](http://tsu-app.rrooaarr.biz/front/mitarbeiter.html).

| column | meaning |
|---|---|
| `time` | time of the reading |
| `counterid` | the app's counter ID |
| `lot` | lot code, e.g. `P10` |
| `capacity` | total spaces |
| `free` | **occupied** spaces, despite the name: free = `capacity - free` |

M1 and M2 share one counter and are logged as `M1`. P23 has no counter and isn't tracked.

**`wifi.csv`**: one row per run, from the kiz [network dashboard](https://grafana.uni-ulm.de/grafana/public-dashboards/c7d386879fae4b97b4dac792b7854d1d).

| column | meaning |
|---|---|
| `time` | time of the reading |
| `eduroam` | devices connected to eduroam |
| `welcome` | devices connected to welcome |

**`traffic.csv`**: network traffic in bits/s, from the same dashboard.

| column | meaning |
|---|---|
| `eduroam_bps`, `welcome_bps` | traffic in the eduroam and welcome Wi-Fi networks |
| `uplink_stg_bps`, `uplink_ka_bps` | the university's 100G internet uplinks via Stuttgart and Karlsruhe |

**`firewall.csv`**: `kizbox01`, `kizbox02`, clients behind the kiz firewalls, from the same dashboard.

**`lectures.csv`**: from the public "events of the day" list of the [course catalogue](https://campusonline.uni-ulm.de/qislsf/rds?state=user&type=0).

| column | meaning |
|---|---|
| `events_now` | entries running right now (includes room blocks like building work) |
| `courses_now` | running entries that have a course number, i.e. actual courses |
| `rooms_in_use` | distinct rooms used by running entries |
| `cancelled_today` | courses listed as cancelled for today |

**`weather.csv`**: current weather at the campus from [Open-Meteo](https://open-meteo.com): `temperature_c`, `precipitation_mm`, `cloud_cover_pct`, `wind_kmh`, `weather_code` ([WMO code](https://open-meteo.com/en/docs#weather_variable_documentation)).

**`transit.csv`**: departures at the stop *Universität Süd* from the [DING](https://www.ding.eu) departure board.

| column | meaning |
|---|---|
| `departures_30min` | departures in the next 30 minutes |
| `realtime_30min` | how many of those have real-time data |
| `avg_delay_min`, `max_delay_min` | delay of those, in minutes |

All files of one run share the same `time`, so they can be joined on it.

Loading the data in pandas (the files mix `+01:00` and `+02:00` offsets, so parse via UTC):

```python
import pandas as pd

d = pd.read_csv("parking.csv")
d["time"] = pd.to_datetime(d.time, utc=True).dt.tz_convert("Europe/Berlin")
d["free_spaces"] = d.capacity - d.free  # the "free" column is occupied spaces

w = pd.read_csv("weather.csv")
w["time"] = pd.to_datetime(w.time, utc=True).dt.tz_convert("Europe/Berlin")
d = d.merge(w, on="time", how="left")
```

## Maintenance

- The GitHub token used by cron-job.org expires on **9 Feb 2027**. Create a new fine-grained token (this repo only, Actions: read and write) and update the `Authorization` header in the cron-job.org job.
- If data stops coming in, check the [Actions tab](https://github.com/raustefan/parkingsim/actions) and https://www.githubstatus.com.
- Run locally with `python3 track.py`. It appends to the CSVs next to the script.
- Grafana panel IDs, the course catalogue URL and the stop name are constants at the top of `track.py`, in case a source changes.
