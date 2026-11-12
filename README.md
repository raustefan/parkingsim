<img src="assets/icon.svg" width="64" height="64" alt="">

# parkingsim

Tracks parking lot occupancy and campus Wi-Fi usage at Ulm University every 5 minutes, to later build a model that predicts how full the lots are by time and weekday.

**Live site:** https://raustefan.github.io/parkingsim/

## How it works

- `track.py` fetches the current counts and appends them to two CSV files. It only needs Python 3, no packages.
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
| `time` | same timestamp as the parking rows of that run |
| `eduroam` | devices connected to eduroam |
| `welcome` | devices connected to welcome |

Loading it in pandas (the file mixes `+01:00` and `+02:00` offsets, so parse via UTC):

```python
import pandas as pd

d = pd.read_csv("parking.csv")
d["time"] = pd.to_datetime(d.time, utc=True).dt.tz_convert("Europe/Berlin")
d["free_spaces"] = d.capacity - d.free  # the "free" column is occupied spaces
```

## Maintenance

- The GitHub token used by cron-job.org expires on **9 Feb 2027**. Create a new fine-grained token (this repo only, Actions: read and write) and update the `Authorization` header in the cron-job.org job.
- If data stops coming in, check the [Actions tab](https://github.com/raustefan/parkingsim/actions) and https://www.githubstatus.com.
- Run locally with `python3 track.py`. It appends to the CSVs next to the script.
