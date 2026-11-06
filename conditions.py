"""Turn the raw data files into the numbers and plain-English flags the dashboard shows."""
import json
from datetime import datetime, timedelta, timezone

import pandas as pd

import config

# North American Public Avalanche Danger Scale, summarized
DANGER = {
    -1: ("No rating", "#898781", "NWAC is not issuing daily ratings yet. Treat any slope with snow as possible avalanche terrain."),
    0: ("No rating", "#898781", "No rating issued for this zone today."),
    1: ("1 - Low", "#0ca30c", "Generally safe conditions. Watch for unstable snow on isolated terrain features."),
    2: ("2 - Moderate", "#fab219", "Heightened conditions on specific terrain features. Evaluate snow and terrain carefully; identify features of concern."),
    3: ("3 - Considerable", "#ec835a", "Dangerous conditions. Careful snowpack evaluation, cautious route-finding, and conservative decisions are essential."),
    4: ("4 - High", "#d03b3b", "Very dangerous conditions. Travel in avalanche terrain is not recommended."),
    5: ("5 - Extreme", "#0b0b0b", "Avoid all avalanche terrain."),
}


def clean_nwac(df):
    """Both snow sensors spike (e.g. 122 in on the ground for one hour, 46 in of new snow on a 12 in base).
    Smooth depth with a 5-hour median, drop new-snow readings larger than the snow on the ground,
    then smooth new snow with a 3-hour median."""
    df = df.copy()
    for elev in ("6230", "5940"):
        s, d = f"snow24_{elev}", f"depth_{elev}"
        df[d] = df[d].rolling(5, center=True, min_periods=1).median()
        df.loc[df[s] > df[d] + 2, s] = None
        df.loc[df[s] < 0, s] = None
        df[s] = df[s].rolling(3, center=True, min_periods=1).median()
    return df


def nwac_summary(df):
    df = clean_nwac(df).set_index("time").sort_index()
    latest = df.index.max()
    s = df["snow24_6230"]

    def reading(at):
        window = s[at - timedelta(hours=1):at + timedelta(hours=1)].dropna()
        return float(window.iloc[-1]) if len(window) else 0.0

    snow24 = reading(latest)
    snow72 = snow24 + reading(latest - timedelta(hours=24)) + reading(latest - timedelta(hours=48))
    # Daily new snow = 24-hr total read at 11 PM (or the last reading that day)
    daily = s.resample("D").last().fillna(0).round(1)
    return {
        "latest": latest,
        "temp_6230": df["temp_6230"].iloc[-1],
        "depth_6230": df["depth_6230"].iloc[-1],
        "depth_5940": df["depth_5940"].iloc[-1],
        "snow24": round(snow24),  # sensor reads whole inches; the median can add a false .5
        "snow72": round(snow72),
        "daily": daily,
        "hourly": df,
    }


def forecast_summary(fc, hours=72):
    h = pd.DataFrame(fc["hourly"])
    h["time"] = pd.to_datetime(h["time"])
    cutoff = datetime.now(timezone.utc) + timedelta(hours=hours)
    next_ = h[h["time"] <= cutoff]
    wet = next_[next_["quantitativePrecipitation"] > 0]  # NWS spreads precip thinly across 6-hr blocks
    return {
        "snow72": round(next_["snowfallAmount"].sum(), 1),
        "precip72": round(next_["quantitativePrecipitation"].sum(), 2),
        "max_snow_level_wet": int(wet["snowLevel"].max()) if len(wet) else None,
        "max_gust": round(next_["windGust"].max()) if next_["windGust"].notna().any() else None,
        "hourly": h,
    }


def avy_summary(avy):
    today = next((d for d in avy["danger"] if d.get("valid_day") == "current"), None)
    if avy["product_type"] != "forecast" or not today:
        levels = {"upper": -1, "middle": -1, "lower": -1}
    else:
        levels = {k: today.get(k) or 0 for k in ("upper", "middle", "lower")}
    return {**avy, "levels": levels, "max_level": max(levels.values())}


def outlook(nwac, fc, avy):
    """Return a list of (status, text) flags. status is good / warning / serious / critical / info."""
    flags = []
    if nwac:
        if nwac["snow24"] >= config.FRESH_24H_IN or nwac["snow72"] >= config.FRESH_72H_IN:
            flags.append(("good", f"Fresh snow: {nwac['snow24']:g} in last 24h, {nwac['snow72']:g} in last 72h at Green Valley."))
        if nwac["depth_6230"] is not None and nwac["depth_6230"] < 24:
            flags.append(("info", f"Thin base: {nwac['depth_6230']:g} in on the ground at 6,230 ft."))
    if fc:
        if fc["snow72"] >= config.FRESH_72H_IN / 2:
            flags.append(("good", f"Snow on the way: about {fc['snow72']:g} in forecast in the next 72h."))
        lvl = fc["max_snow_level_wet"]
        if lvl and lvl > config.RAIN_SNOW_LEVEL_FT:
            flags.append(("warning", f"Rain risk: snow level up to {lvl:,} ft while precipitation is falling "
                                     f"(base {config.BASE_FT:,} ft, summit {config.SUMMIT_FT:,} ft)."))
        if fc["max_gust"] and fc["max_gust"] >= config.WIND_HOLD_GUST_MPH:
            flags.append(("warning", f"Wind: gusts to {fc['max_gust']} mph in the next 72h. Upper lifts may go on hold."))
    if avy and avy["max_level"] >= 3:
        flags.append(("serious", f"Avalanche danger {DANGER[avy['max_level']][0]} in {config.AVY_ZONE_NAME}. "
                                 "Conservative terrain choices outside the ropes."))
    if not flags:
        flags.append(("info", "Nothing notable: no big storm, no rain, no wind holds flagged."))
    return flags


def load():
    """Load every source. A missing or broken source comes back as None so the dashboard still builds."""
    out = {}
    try:
        out["nwac"] = nwac_summary(pd.read_csv(config.DATA / "nwac_hourly.csv", parse_dates=["time"]))
    except Exception as e:
        out["nwac"], out["nwac_error"] = None, str(e)
    try:
        out["snotel"] = pd.read_csv(config.DATA / "snotel_daily.csv", parse_dates=["date"])
    except Exception as e:
        out["snotel"], out["snotel_error"] = None, str(e)
    try:
        fc = json.loads((config.DATA / "forecast_latest.json").read_text())
        out["forecast"] = {**fc, **forecast_summary(fc)}
    except Exception as e:
        out["forecast"], out["forecast_error"] = None, str(e)
    try:
        out["avy"] = avy_summary(json.loads((config.DATA / "avalanche_latest.json").read_text()))
    except Exception as e:
        out["avy"], out["avy_error"] = None, str(e)
    out["flags"] = outlook(out["nwac"], out["forecast"], out["avy"])
    return out
