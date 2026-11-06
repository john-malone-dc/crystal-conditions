"""Pull the NWS text forecast and hourly grid for Crystal into data/forecast_latest.json."""
import json
import re
from datetime import datetime, timedelta, timezone

import requests

import config
import status

OUT = config.DATA / "forecast_latest.json"
GRID_FIELDS = ["temperature", "snowLevel", "snowfallAmount", "quantitativePrecipitation",
               "probabilityOfPrecipitation", "windSpeed", "windGust"]


def get(url):
    r = requests.get(url, headers={"User-Agent": config.USER_AGENT, "Accept": "application/geo+json"},
                     timeout=config.TIMEOUT)
    r.raise_for_status()
    return r.json()["properties"]


def parse_duration(text):
    """ISO durations like 'PT6H' or 'P1DT3H' -> hours."""
    m = re.match(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?)?", text)
    return int(m.group(1) or 0) * 24 + int(m.group(2) or 0)


def expand_hourly(values, spread):
    """Grid values cover time spans; turn them into one value per hour.
    spread=True splits totals (snowfall, precip) evenly across the span."""
    hourly = {}
    for v in values:
        start, dur = v["validTime"].split("/")
        hours = max(parse_duration(dur), 1)
        t0 = datetime.fromisoformat(start)
        val = v["value"]
        for h in range(hours):
            hourly[(t0 + timedelta(hours=h)).isoformat()] = (val / hours if spread and val is not None else val)
    return hourly


def to_imperial(field, val):
    if val is None:
        return None
    if field == "temperature":
        return round(val * 9 / 5 + 32, 1)
    if field == "snowLevel":
        return round(val * 3.28084)
    if field in ("snowfallAmount", "quantitativePrecipitation"):
        return round(val / 25.4, 3)
    if field in ("windSpeed", "windGust"):
        return round(val * 0.621371, 1)
    return val


def main():
    config.DATA.mkdir(exist_ok=True)
    periods = get(config.NWS_GRID + "/forecast")["periods"]
    grid = get(config.NWS_GRID)

    expanded = {f: expand_hourly(grid[f]["values"], f in ("snowfallAmount", "quantitativePrecipitation"))
                for f in GRID_FIELDS if grid.get(f)}
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    hourly = []
    for h in range(7 * 24):
        t = (now + timedelta(hours=h)).isoformat()
        hourly.append({"time": t, **{f: to_imperial(f, expanded[f].get(t)) for f in expanded}})

    out = {
        "fetched": datetime.now().isoformat(timespec="minutes"),
        "periods": [{**{k: p[k] for k in ("name", "startTime", "isDaytime", "temperature", "windSpeed",
                                          "shortForecast", "detailedForecast")},
                     "pop": (p.get("probabilityOfPrecipitation") or {}).get("value")}
                    for p in periods],
        "hourly": hourly,
    }
    OUT.write_text(json.dumps(out, indent=1))
    status.mark("forecast")
    print(f"NWS: {len(out['periods'])} forecast periods, {len(hourly)} hourly rows saved")


if __name__ == "__main__":
    main()
