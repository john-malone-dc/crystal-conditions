"""Scrape the NWAC Crystal Green Valley 7-day table and append it to data/nwac_hourly.csv."""
import io
from datetime import datetime

import pandas as pd
import requests

import config
import status

OUT = config.DATA / "nwac_hourly.csv"
COLUMNS = {
    "Time (PDT)": "time",
    "Temp°F6230'": "temp_6230",
    "Temp°F5940'": "temp_5940",
    "RH%6230'": "rh_6230",
    "24Snoin6230'": "snow24_6230",
    "SnoHtin6230'": "depth_6230",
    "24Snoin5940'": "snow24_5940",
    "SnoHtin5940'": "depth_5940",
}


def parse_time(label, now):
    """Table times look like '10/29 12:00' with no year; assume the most recent past date."""
    t = datetime.strptime(f"{now.year}/{label}", "%Y/%m/%d %H:%M")
    if t > now:  # e.g. a '12/31' row read on Jan 2
        t = t.replace(year=now.year - 1)
    return t


def fetch():
    r = requests.get(config.NWAC_URL, headers={"User-Agent": config.USER_AGENT}, timeout=config.TIMEOUT)
    r.raise_for_status()
    df = pd.read_html(io.StringIO(r.text))[0]
    # Header text varies slightly (e.g. "Time (PST)" in winter), so match on the start of each name
    rename = {}
    for col in df.columns:
        for src, dst in COLUMNS.items():
            if col.replace("PST", "PDT") == src:
                rename[col] = dst
    df = df.rename(columns=rename)[[c for c in COLUMNS.values() if c in rename.values()]]
    now = datetime.now()
    df["time"] = [parse_time(str(x), now) for x in df["time"]]
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def main():
    config.DATA.mkdir(exist_ok=True)
    new = fetch()
    if OUT.exists():
        old = pd.read_csv(OUT, parse_dates=["time"])
        new = pd.concat([old, new]).drop_duplicates("time", keep="last")
    new = new.sort_values("time")
    new.to_csv(OUT, index=False)
    status.mark("nwac")
    print(f"NWAC: {len(new)} hourly rows saved, latest {new['time'].max()}")


if __name__ == "__main__":
    main()
