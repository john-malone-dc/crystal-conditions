"""Pull daily Corral Pass SNOTEL data into data/snotel_daily.csv (full history on first run)."""
from datetime import date, timedelta

import pandas as pd
import requests

import config
import status

OUT = config.DATA / "snotel_daily.csv"
ELEMENTS = {"SNWD": "snow_depth_in", "WTEQ": "swe_in", "PREC": "precip_accum_in", "TOBS": "temp_f"}


def fetch(begin, end):
    params = {
        "stationTriplets": config.SNOTEL_TRIPLET,
        "elements": ",".join(ELEMENTS),
        "duration": "DAILY",
        "beginDate": begin,
        "endDate": end,
    }
    r = requests.get(config.SNOTEL_API, params=params, headers={"User-Agent": config.USER_AGENT},
                     timeout=config.TIMEOUT * 3)
    r.raise_for_status()
    frames = []
    for element in r.json()[0]["data"]:
        code = element["stationElement"]["elementCode"]
        s = pd.DataFrame(element["values"])
        if s.empty:
            continue
        frames.append(s.set_index("date")["value"].rename(ELEMENTS[code]))
    df = pd.concat(frames, axis=1).reset_index().rename(columns={"index": "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df


def main():
    config.DATA.mkdir(exist_ok=True)
    today = date.today().isoformat()
    if OUT.exists():
        old = pd.read_csv(OUT, parse_dates=["date"])
        begin = (old["date"].max() - timedelta(days=14)).date().isoformat()
        df = pd.concat([old, fetch(begin, today)]).drop_duplicates("date", keep="last")
    else:
        df = fetch(config.SNOTEL_START, today)
    df = df.sort_values("date")
    df.to_csv(OUT, index=False)
    status.mark("snotel")
    print(f"SNOTEL: {len(df)} daily rows saved, {df['date'].min().date()} to {df['date'].max().date()}")


if __name__ == "__main__":
    main()
