"""Render dashboard.html from the data files. Charts use Chart.js (loaded from a CDN)."""
import html
import json
from datetime import date, datetime, timedelta

import pandas as pd

import conditions
import config
import status

STALE_HOURS = 26


def season_start(d):
    return date(d.year if d.month >= 10 else d.year - 1, 10, 1)


def season_label(start):
    return f"{start.year}-{str(start.year + 1)[2:]}"


def snow_history(snotel):
    """Snow depth by day of season (Oct 1 - Jun 30): this season, last season, and the range of past seasons."""
    df = snotel.dropna(subset=["snow_depth_in"]).copy()
    df["start"] = df["date"].dt.date.map(season_start)
    df["day"] = (df["date"].dt.date - df["start"]).map(lambda x: x.days)
    df = df[df["day"] < 273]
    this = season_start(date.today())
    last = date(this.year - 1, 10, 1)
    past = df[df["start"] < this]
    by_day = past.groupby("day")["snow_depth_in"]
    days = list(range(273))
    labels = [(date(2025, 10, 1) + timedelta(days=i)).strftime("%b %d") for i in days]

    def series(start):
        s = df[df["start"] == start].set_index("day")["snow_depth_in"]
        return [None if pd.isna(v) else float(v) for v in s.reindex(days)]

    stats = {k: [None if pd.isna(v) else round(float(v), 1) for v in getattr(by_day, k)().reindex(days)]
             for k in ("median", "min", "max")}
    n_seasons = past["start"].nunique()
    # Peak snowpack (SWE) per season - SWE record goes back further than snow depth
    swe = snotel.dropna(subset=["swe_in"]).copy()
    swe["season"] = swe["date"].dt.date.map(lambda d: season_label(season_start(d)))
    peaks = swe.groupby("season")["swe_in"].max().round(1)
    peaks = peaks[peaks.index >= "1980-81"]
    return {
        "labels": labels, "this": series(this), "last": series(last), **stats,
        "this_label": season_label(this), "last_label": season_label(last), "n_seasons": int(n_seasons),
        "first_season": season_label(past["start"].min()),
        "peak_labels": list(peaks.index), "peak_values": [float(v) for v in peaks.values],
        "median_peak": round(float(peaks[peaks.index != season_label(this)].median()), 1),
    }


def forecast_charts(fc):
    """Both forecast charts share an x-axis of hours from now (0-72) so they line up vertically."""
    h = fc["hourly"].copy()
    h["local"] = h["time"].dt.tz_convert("America/Los_Angeles")
    h = h[h["time"] < h["time"].min() + pd.Timedelta(hours=72)].reset_index(drop=True)
    start = h["local"].iloc[0]
    is_rain = h["snowLevel"] > config.RAIN_SNOW_LEVEL_FT
    h["rain"] = h["quantitativePrecipitation"].where(is_rain, 0.0)  # NWS gives no rain field: precip in rain hours
    six = h.set_index("local").resample("6h")[["snowfallAmount", "rain"]].sum().round(2)
    hours_in = [(t - start) / pd.Timedelta(hours=1) + 3 for t in six.index]
    return {
        "hour_labels": [t.strftime("%a %I %p").replace(" 0", " ") for t in h["local"]],
        "ticks": [i for i, t in enumerate(h["local"]) if t.hour in (0, 12)],
        "level": [{"x": i, "y": None if pd.isna(v) else int(v), "kind": ("rain" if r else "snow") if q > 0 else None}
                  for i, (v, q, r) in enumerate(zip(h["snowLevel"], h["quantitativePrecipitation"], is_rain))],
        "snow": [{"x": x, "y": float(v)} for x, v in zip(hours_in, six["snowfallAmount"])],
        "rain": [{"x": x, "y": float(v)} for x, v in zip(hours_in, six["rain"])],
    }


def forecast_table(fc):
    """One row per day (6 AM to 6 AM, so each day pairs with the night after it).
    NWS text periods give sky and high/low; the hourly grid gives snow, snow level and gusts."""
    tz = "America/Los_Angeles"
    h = fc["hourly"].copy()
    h["day"] = (h["time"].dt.tz_convert(tz) - pd.Timedelta(hours=6)).dt.date
    days = {}
    for p in fc["periods"]:
        if "startTime" not in p:  # forecast file from before this column existed
            return ""
        day = (pd.Timestamp(p["startTime"]).tz_convert(tz) - pd.Timedelta(hours=6)).date()
        days.setdefault(day, {})["day" if p["isDaytime"] else "night"] = p

    today = (pd.Timestamp.now(tz) - pd.Timedelta(hours=6)).date()
    rows = ""
    for i, (day, pair) in enumerate(sorted(days.items())):
        hrs = h[h["day"] == day]
        wet = hrs[hrs["quantitativePrecipitation"] > 0]
        snow = hrs["snowfallAmount"].sum()
        rain = wet.loc[wet["snowLevel"] > config.RAIN_SNOW_LEVEL_FT, "quantitativePrecipitation"].sum()
        gust = hrs["windGust"].max()
        d, n = pair.get("day"), pair.get("night")
        name = "Today" if day == today else day.strftime("%a %b %d").replace(" 0", " ")
        temps = f'{d["temperature"] if d else "–"}° / {n["temperature"] if n else "–"}°'
        sky = html.escape(d["shortForecast"]) if d else ""
        if n:
            sky += f'<div class="muted">Night: {html.escape(n["shortForecast"])}</div>'
        pops = [p["pop"] for p in (d, n) if p and p.get("pop") is not None]
        snow_cell = f'{snow:.1f}"' if snow >= 0.05 else "–"
        if snow >= 1:
            snow_cell = f"<strong>{snow_cell}</strong>"
        rain_cell = f'{rain:.2f}"' if rain >= 0.005 else "–"
        if len(wet):
            lvl = int(wet["snowLevel"].max())
            level_cell = f"{lvl:,} ft"
            if lvl > config.RAIN_SNOW_LEVEL_FT:
                level_cell = f'<span class="warn-text">! {level_cell} rain risk</span>'
        else:
            level_cell = '<span class="muted">dry</span>'
        gust_cell = "–" if pd.isna(gust) else f"{gust:.0f} mph"
        if not pd.isna(gust) and gust >= config.WIND_HOLD_GUST_MPH:
            gust_cell = f'<span class="warn-text">! {gust_cell}</span>'
        detail = "".join(f'<p><strong>{html.escape(p["name"])}:</strong> {html.escape(p["detailedForecast"])}</p>'
                         for p in (d, n) if p)
        rows += (f'<tr class="fc-row" data-i="{i}"><td class="fc-day"><span class="caret">▸</span>{name}</td>'
                 f'<td class="num">{temps}</td><td>{sky}</td><td class="num">{max(pops) if pops else 0}%</td>'
                 f'<td class="num">{snow_cell}</td><td class="num">{rain_cell}</td><td class="num">{level_cell}</td>'
                 f'<td class="num">{gust_cell}</td></tr>'
                 f'<tr class="fc-detail" id="fc-detail-{i}" hidden><td colspan="8">{detail}</td></tr>')
    return f"""<div class="table-wrap"><table class="fc">
      <thead><tr><th>Day</th><th class="num">High / Low</th><th>Sky</th><th class="num">Precip chance</th>
        <th class="num">Snow</th><th class="num">Rain</th><th class="num">Snow level</th><th class="num">Max gust</th></tr></thead>
      <tbody>{rows}</tbody></table></div>
      <div class="muted">Click a day for the NWS wording. Snow, rain, snow level and gusts come from the NWS hourly grid;
        rain is inches of water from hours when the snow level is above {config.RAIN_SNOW_LEVEL_FT:,} ft;
        snow level shows the highest it gets while precipitation is falling.</div>"""


def nwac_charts(nwac):
    daily = nwac["daily"]
    daily = daily[daily.index.date >= season_start(date.today())]
    h = nwac["hourly"]
    h = h[h.index >= h.index.max() - pd.Timedelta(days=7)]
    return {
        "daily_labels": [d.strftime("%b %d") for d in daily.index],
        "daily_values": [float(v) for v in daily.values],
        "depth_labels": [t.strftime("%a %I%p").replace(" 0", " ") for t in h.index],
        "depth_6230": [None if pd.isna(v) else float(v) for v in h["depth_6230"]],
        "depth_5940": [None if pd.isna(v) else float(v) for v in h["depth_5940"]],
    }


def updated(source):
    stamp = status.read().get(source)
    if not stamp:
        return '<span class="stale">No data yet</span>'
    t = datetime.fromisoformat(stamp)
    text = f"Updated {t:%a %b %d, %I:%M %p}"
    if datetime.now() - t > timedelta(hours=STALE_HOURS):
        return f'<span class="stale">⚠ Stale - {text}. The latest refresh of this source failed.</span>'
    return f'<span class="muted">{text}</span>'


def error_box(d, key):
    err = d.get(f"{key}_error")
    return f'<p class="stale">⚠ Could not load this section: {html.escape(err)}</p>' if err else ""


def tile(label, value, note=""):
    return (f'<div class="tile"><div class="tile-label">{label}</div><div class="tile-value">{value}</div>'
            f'<div class="tile-note">{note}</div></div>')


def fmt(v, unit="", digits=0):
    if v is None or pd.isna(v):
        return "–"
    return f"{v:,.{digits}f}{unit}"


def build():
    d = conditions.load()
    nwac, fc, avy, snotel = d["nwac"], d["forecast"], d["avy"], d["snotel"]
    charts = {}
    if snotel is not None:
        charts["history"] = snow_history(snotel)
    if fc:
        charts["forecast"] = forecast_charts(fc)
    if nwac:
        charts["nwac"] = nwac_charts(nwac)

    icons = {"good": "▲", "warning": "!", "serious": "!!", "critical": "!!!", "info": "•"}
    flags_html = "".join(f'<li class="flag {s}"><span class="flag-icon">{icons[s]}</span>{html.escape(t)}</li>'
                         for s, t in d["flags"])

    tiles = ""
    if nwac:
        tiles += tile("New snow, 24h", fmt(nwac["snow24"], '"', 0), "Green Valley 6,230 ft")
        tiles += tile("New snow, 72h", fmt(nwac["snow72"], '"', 0), "Green Valley 6,230 ft")
        tiles += tile("Snow on ground", fmt(nwac["depth_6230"], '"'), f'{fmt(nwac["depth_5940"], chr(34))} at 5,940 ft')
        tiles += tile("Temp now", fmt(nwac["temp_6230"], "°F"), f'as of {nwac["latest"]:%a %I:%M %p}')
    if fc:
        tiles += tile("Forecast snow, 72h", fmt(fc["snow72"], '"', 1), f'{fmt(fc["precip72"], " in", 2)} water')
        tiles += tile("Max gust, 72h", fmt(fc["max_gust"], " mph"), "NWS forecast")

    fc_table = forecast_table(fc) if fc else ""

    avy_html = ""
    if avy:
        bands = [("Above treeline", "upper"), ("Near treeline", "middle"), ("Below treeline", "lower")]
        rows = ""
        for name, key in bands:
            label, color, _ = conditions.DANGER.get(avy["levels"][key], conditions.DANGER[0])
            rows += (f'<div class="danger-row"><span class="danger-chip" style="background:{color}"></span>'
                     f'<span class="danger-band">{name}</span><span class="danger-level">{label}</span></div>')
        top_label, _, advice = conditions.DANGER.get(avy["max_level"], conditions.DANGER[0])
        statement = ("Daily forecast" if avy["product_type"] == "forecast"
                     else "Off-season statement - no daily danger ratings yet")
        expires = ""
        if avy.get("expires"):
            until = pd.Timestamp(avy["expires"]).tz_convert("America/Los_Angeles")
            expires = f' · valid until {until.strftime("%a %b %d, %I:%M %p").replace(" 0", " ")}'
        avy_html = f"""
          <p class="muted">{statement}{expires}</p>
          <div class="danger">{rows}</div>
          <div class="advice"><strong>What {top_label} means:</strong> {advice}</div>
          <p><a href="{config.AVY_PAGE}"><strong>Read NWAC's full forecast for {config.AVY_ZONE_NAME}</strong></a></p>
          <h3>Recommendations</h3>
          <ul>
            <li>Inside the ropes, Crystal ski patrol does avalanche control. Respect closures and rope lines.</li>
            <li>Past the ski area boundary gates you are in uncontrolled terrain: carry beacon, shovel, probe, and ski with a partner.</li>
            <li>This page shows NWAC's rating only. It does not replace reading their forecast or taking an avalanche course.</li>
          </ul>"""

    h = charts.get("history")
    history_note = ""
    if h:
        history_note = (f'Corral Pass SNOTEL, 5,810 ft, about 6 miles north of Crystal. Gray band = range of '
                        f'{h["n_seasons"]} past seasons ({h["first_season"]} on); dashed = median.')

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crystal Ski Conditions</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root {{
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
  --series-1: #2a78d6; --series-2: #eb6834; --band: rgba(137,135,129,0.18); --mountain: rgba(82,81,78,0.13);
  --good: #006300; --warning: #9a6a00; --serious: #b4542d; --critical: #d03b3b;
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) {{
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
    --series-1: #3987e5; --series-2: #d95926; --band: rgba(195,194,183,0.14); --mountain: rgba(195,194,183,0.16);
    --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --critical: #e66767;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
  --series-1: #3987e5; --series-2: #d95926; --band: rgba(195,194,183,0.14); --mountain: rgba(195,194,183,0.16);
  --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --critical: #e66767;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--page); color: var(--ink); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 24px 16px 48px; }}
h1 {{ font-size: 26px; margin: 0 0 4px; }}
h2 {{ font-size: 19px; margin: 0 0 4px; }}
h3 {{ font-size: 15px; margin: 18px 0 6px; }}
a {{ color: var(--series-1); }}
.muted {{ color: var(--muted); font-size: 13px; }}
.stale {{ color: var(--critical); font-size: 13px; font-weight: 600; }}
.card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-top: 20px; }}
.card-head {{ display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
.flags {{ list-style: none; padding: 0; margin: 0 0 16px; }}
.flag {{ display: flex; gap: 10px; padding: 6px 0; }}
.flag-icon {{ font-weight: 700; min-width: 22px; text-align: center; }}
.flag.good .flag-icon {{ color: var(--good); }} .flag.warning .flag-icon {{ color: var(--warning); }}
.flag.serious .flag-icon {{ color: var(--serious); }} .flag.critical .flag-icon {{ color: var(--critical); }}
.flag.info .flag-icon {{ color: var(--muted); }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }}
.tile {{ border: 1px solid var(--border); border-radius: 10px; padding: 12px; }}
.tile-label {{ color: var(--ink-2); font-size: 13px; }}
.tile-value {{ font-size: 28px; font-weight: 600; }}
.tile-note {{ color: var(--muted); font-size: 12px; }}
.charts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }}
.chart-box h3 {{ margin-top: 0; }}
.chart {{ position: relative; height: 260px; }}
.chart.tall {{ height: 340px; }}
.chart.short {{ height: 150px; }}
@media (max-width: 600px) {{  /* phones: shorter charts so more fits on screen */
  .chart {{ height: 200px; }}
  .chart.tall {{ height: 240px; }}
  .chart.short {{ height: 120px; }}
}}
.key {{ display: flex; flex-wrap: wrap; gap: 16px; font-size: 13px; color: var(--ink-2); margin-bottom: 6px; }}
.key span {{ display: inline-flex; align-items: center; gap: 6px; }}
.swatch {{ display: inline-block; width: 18px; height: 3px; border-radius: 2px; }}
.swatch.dashed {{ height: 0; border-top: 2px dashed var(--muted); }}
.key span:last-child .swatch {{ height: 12px; }}
.table-wrap {{ overflow-x: auto; margin: 0 0 6px; }}
table.fc {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.fc th {{ text-align: left; color: var(--ink-2); font-weight: 600; font-size: 13px; padding: 8px 10px; border-bottom: 1px solid var(--axis); white-space: nowrap; }}
.fc td {{ padding: 8px 10px; border-bottom: 1px solid var(--grid); vertical-align: top; }}
.fc .num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.fc-row {{ cursor: pointer; }} .fc-row:hover {{ background: var(--page); }}
.fc-day {{ font-weight: 600; white-space: nowrap; }}
.caret {{ display: inline-block; width: 14px; color: var(--muted); transition: transform .15s; }}
.fc-row.open .caret {{ transform: rotate(90deg); }}
.fc-detail td {{ background: var(--page); color: var(--ink-2); font-size: 13px; }}
.fc-detail p {{ margin: 4px 0; }}
.warn-text {{ color: var(--warning); font-weight: 600; }}
.danger {{ display: grid; gap: 6px; margin: 12px 0; }}
.danger-row {{ display: flex; align-items: center; gap: 10px; }}
.danger-chip {{ width: 18px; height: 18px; border-radius: 4px; }}
.danger-band {{ min-width: 130px; color: var(--ink-2); }}
.danger-level {{ font-weight: 600; }}
.advice {{ padding: 12px; border-left: 3px solid var(--axis); background: var(--page); border-radius: 4px; }}
</style>
</head>
<body>
<main>
  <h1>Crystal Mountain Ski Conditions</h1>
  <div class="muted">Built {datetime.now():%A %B %d, %Y at %I:%M %p} ·
    Sources: <a href="{config.NWAC_PAGE}">NWAC Green Valley</a>, <a href="{config.NWS_PAGE}">NWS forecast</a>,
    <a href="{config.AVY_PAGE}">NWAC avalanche</a>, NRCS SNOTEL Corral Pass</div>

  <section class="card">
    <div class="card-head"><h2>Today's outlook</h2>{updated("nwac")}</div>
    {error_box(d, "nwac")}
    <ul class="flags">{flags_html}</ul>
    <div class="tiles">{tiles}</div>
  </section>

  <section class="card">
    <div class="card-head"><h2>Forecast</h2>{updated("forecast")}</div>
    {error_box(d, "forecast")}
    <div class="chart-box">
      <h3>Snow level (ft), next 72 hours</h3>
      <div class="key">
        <span><i class="swatch" style="background:var(--series-2)"></i>Rain: snow level above {config.RAIN_SNOW_LEVEL_FT:,} ft</span>
        <span><i class="swatch" style="background:var(--series-1)"></i>Snow: snow level at or below {config.RAIN_SNOW_LEVEL_FT:,} ft</span>
        <span><i class="swatch dashed"></i>Dry</span>
        <span><i class="swatch" style="background:var(--mountain)"></i>Crystal, base to summit</span>
      </div>
      <div class="chart"><canvas id="fcLevel"></canvas></div>
      <div class="muted">Color uses one cutoff for the whole mountain. When the line is inside the shaded band, rain falls below it and snow above.</div>
      <h3 style="margin-top:16px">Forecast snow and rain per 6 hours (in)</h3>
      <div class="key">
        <span><i class="swatch" style="background:var(--series-1);height:12px"></i>Snow, inches of snowfall</span>
        <span><i class="swatch" style="background:var(--series-2)"></i>Rain, inches of water</span>
      </div>
      <div class="chart short"><canvas id="fcSnow"></canvas></div>
      <div class="muted">Rain is NWS precipitation in hours when the snow level is above {config.RAIN_SNOW_LEVEL_FT:,} ft. An inch of rain holds about as much water as 10 in of snow. Scale starts at {config.FORECAST_SNOW_SCALE_IN:g} in, so small amounts look small. It grows if a bigger storm is forecast.</div>
    </div>
    {fc_table}
  </section>

  <section class="card">
    <div class="card-head"><h2>Avalanche - {config.AVY_ZONE_NAME}</h2>{updated("avalanche")}</div>
    {error_box(d, "avy")}
    {avy_html}
  </section>

  <section class="card">
    <div class="card-head"><h2>Snow history</h2>{updated("snotel")}</div>
    {error_box(d, "snotel")}
    <div class="chart-box"><h3>Snow depth by date (in) - this season vs past seasons</h3>
      <div class="chart tall"><canvas id="history"></canvas></div>
      <div class="muted">{history_note}</div></div>
    <div class="charts" style="margin-top:20px">
      <div class="chart-box"><h3>Green Valley daily new snow this season (in)</h3><div class="chart"><canvas id="daily"></canvas></div>
        <div class="muted">From the NWAC 24-hr snow sensor; history builds up one week at a time as the app runs.</div></div>
      <div class="chart-box"><h3>Green Valley snow on ground, last 7 days (in)</h3><div class="chart"><canvas id="depth7"></canvas></div></div>
    </div>
    <div class="chart-box" style="margin-top:20px"><h3>Peak snowpack each season - snow water equivalent (in), Corral Pass</h3>
      <div class="chart"><canvas id="peaks"></canvas></div>
      <div class="muted">Water content of the deepest snowpack each season; better than depth for comparing years. Median {h["median_peak"] if h else "–"} in.</div></div>
  </section>
</main>
<script>
const DATA = {json.dumps(charts)};
document.querySelectorAll('.fc-row').forEach(r => r.addEventListener('click', () => {{
  const detail = document.getElementById('fc-detail-' + r.dataset.i);
  detail.hidden = !detail.hidden;
  r.classList.toggle('open', !detail.hidden);
}}));
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
if (window.Chart) {{
  Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", sans-serif';
  Chart.defaults.color = css('--muted');
  Chart.defaults.borderColor = css('--grid');
  Chart.defaults.plugins.tooltip.mode = 'index';
  Chart.defaults.plugins.tooltip.intersect = false;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.elements.line.borderWidth = 2;
  Chart.defaults.elements.point.radius = 0;
  Chart.defaults.elements.point.hoverRadius = 5;
  Chart.defaults.elements.bar.borderRadius = {{topLeft: 4, topRight: 4}};
  const noLegend = {{legend: {{display: false}}}};
  const ticks = n => ({{autoSkip: true, maxTicksLimit: n, maxRotation: 0}});
  const bar = (id, labels, values, unit, color) => new Chart(document.getElementById(id), {{
    type: 'bar',
    data: {{labels, datasets: [{{label: unit, data: values, backgroundColor: color, categoryPercentage: 0.9, barPercentage: 0.9}}]}},
    options: {{plugins: noLegend, scales: {{x: {{grid: {{display: false}}, ticks: ticks(8)}}, y: {{beginAtZero: true}}}}}}
  }});

  const f = DATA.forecast;
  if (f) {{
    // Shared x-axis: hours from now, ticks at midnight and noon, fixed y-axis width so both charts line up
    const xAxis = {{
      type: 'linear', min: 0, max: 72, grid: {{color: css('--grid')}},
      afterBuildTicks: a => {{ a.ticks = f.ticks.map(v => ({{value: v}})); }},
      ticks: {{maxRotation: 0, callback: v => f.hour_labels[v]}},
    }};
    const yWidth = {{afterFit: a => {{ a.width = 60; }}}};
    const hoverTitle = items => f.hour_labels[Math.round(items[0].parsed.x)] || '';
    const mountainLabels = {{
      id: 'mountainLabels',
      afterDatasetsDraw(chart) {{
        const {{ctx, chartArea: area, scales: {{y}}}} = chart;
        ctx.save();
        ctx.font = '600 12px system-ui, -apple-system, "Segoe UI", sans-serif';
        ctx.fillStyle = css('--ink-2');
        ctx.textAlign = 'left';
        ctx.fillText('Summit {config.SUMMIT_FT:,} ft', area.left + 6, y.getPixelForValue({config.SUMMIT_FT}) - 6);
        ctx.fillText('Base {config.BASE_FT:,} ft', area.left + 6, y.getPixelForValue({config.BASE_FT}) + 15);
        ctx.restore();
      }}
    }};
    const ridge = v => [{{x: 0, y: v}}, {{x: 72, y: v}}];
    const kind = c => f.level[c.p0DataIndex].kind || f.level[c.p1DataIndex].kind;
    const kindColor = {{rain: css('--series-2'), snow: css('--series-1')}};
    new Chart(document.getElementById('fcLevel'), {{
      type: 'line',
      plugins: [mountainLabels],
      data: {{datasets: [
        {{label: 'Snow level', data: f.level, borderWidth: 2.5, tension: 0.3, borderColor: css('--series-1'),
          segment: {{borderColor: c => kindColor[kind(c)] || css('--muted'), borderDash: c => kind(c) ? [] : [5, 4]}}}},
        {{label: 'Summit', data: ridge({config.SUMMIT_FT}), borderColor: css('--ink-2'), borderWidth: 2,
          backgroundColor: css('--mountain'), fill: '+1'}},
        {{label: 'Base', data: ridge({config.BASE_FT}), borderColor: css('--ink-2'), borderWidth: 2}},
      ]}},
      options: {{
        parsing: false,
        plugins: {{legend: {{display: false}}, tooltip: {{
          filter: i => i.datasetIndex === 0,
          callbacks: {{title: hoverTitle,
            label: i => `Snow level ${{i.parsed.y.toLocaleString()}} ft · ${{f.level[i.dataIndex].kind || 'dry'}}`}}
        }}}},
        interaction: {{mode: 'nearest', axis: 'x', intersect: false}},
        scales: {{x: {{...xAxis}}, y: {{...yWidth, suggestedMin: 2000, suggestedMax: 8000, ticks: {{callback: v => v.toLocaleString()}}}}}}
      }}
    }});
    new Chart(document.getElementById('fcSnow'), {{
      type: 'bar',
      data: {{datasets: [
        {{label: 'snow', data: f.snow, backgroundColor: css('--series-1'), barPercentage: 0.9, categoryPercentage: 1}},
        {{label: 'rain', data: f.rain, backgroundColor: css('--series-2'), barPercentage: 0.9, categoryPercentage: 1}},
      ]}},
      options: {{
        plugins: {{legend: {{display: false}}, tooltip: {{callbacks: {{
          title: items => 'Starting ' + (f.hour_labels[Math.max(0, Math.round(items[0].parsed.x - 3))] || ''),
          label: i => `${{i.parsed.y}} in of ${{i.dataset.label}} in 6 hours`}}}}}},
        interaction: {{mode: 'nearest', axis: 'x', intersect: false}},
        scales: {{x: {{...xAxis, stacked: true}}, y: {{...yWidth, stacked: true, min: 0, suggestedMax: {config.FORECAST_SNOW_SCALE_IN}}}}}
      }}
    }});
  }}

  const h = DATA.history;
  if (h) {{
    new Chart(document.getElementById('history'), {{
      type: 'line',
      data: {{labels: h.labels, datasets: [
        {{label: h.this_label, data: h.this, borderColor: css('--series-1'), borderWidth: 2.5}},
        {{label: h.last_label, data: h.last, borderColor: css('--series-2')}},
        {{label: 'Median', data: h.median, borderColor: css('--muted'), borderDash: [5, 4], borderWidth: 1.5}},
        {{label: 'Max', data: h.max, borderColor: 'transparent', backgroundColor: css('--band'), fill: '+1'}},
        {{label: 'Min', data: h.min, borderColor: 'transparent'}},
      ]}},
      options: {{
        plugins: {{legend: {{labels: {{filter: i => !['Max', 'Min'].includes(i.text), boxHeight: 2}}}}}},
        scales: {{x: {{grid: {{display: false}}, ticks: ticks(10)}}, y: {{beginAtZero: true}}}}
      }}
    }});
    bar('peaks', h.peak_labels, h.peak_values, 'Peak SWE (in)',
        h.peak_labels.map(l => l === h.this_label ? css('--series-1') : css('--axis')));
  }}

  const n = DATA.nwac;
  if (n) {{
    bar('daily', n.daily_labels, n.daily_values, 'New snow (in)', css('--series-1'));
    new Chart(document.getElementById('depth7'), {{
      type: 'line',
      data: {{labels: n.depth_labels, datasets: [
        {{label: "6,230 ft", data: n.depth_6230, borderColor: css('--series-1')}},
        {{label: "5,940 ft", data: n.depth_5940, borderColor: css('--series-2')}},
      ]}},
      options: {{plugins: {{legend: {{labels: {{boxHeight: 2}}}}}}, scales: {{x: {{grid: {{display: false}}, ticks: ticks(7)}}, y: {{beginAtZero: true}}}}}}
    }});
  }}
}} else {{
  document.querySelectorAll('canvas').forEach(c => c.replaceWith(Object.assign(document.createElement('p'),
    {{className: 'stale', textContent: 'Charts need an internet connection (Chart.js could not load).'}})));
}}
</script>
</body>
</html>"""
    config.DASHBOARD.write_text(page, encoding="utf-8")
    print(f"Dashboard written to {config.DASHBOARD}")


if __name__ == "__main__":
    build()
