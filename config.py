"""Settings for the Crystal Mountain conditions dashboard. Edit thresholds here."""
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
LOGS = ROOT / "logs"
NWAC_ARCHIVE = DATA / "nwac_archive"
DASHBOARD = ROOT / "dashboard.html"

USER_AGENT = "crystal-conditions ski dashboard (https://github.com/john-malone-dc/crystal-conditions)"
TIMEOUT = 60

# Crystal Mountain
BASE_FT = 4400
SUMMIT_FT = 7012

# NWAC Green Valley station (scraped once per run)
NWAC_URL = "https://nwac.us/weather/stations/crystal-mt-green-valley?range=table&period=7d"
NWAC_PAGE = "https://nwac.us/weather/stations/crystal-mt-green-valley"

# NRCS SNOTEL - Corral Pass, 5,810 ft, ~6 mi north of Crystal
SNOTEL_TRIPLET = "418:WA:SNTL"
SNOTEL_API = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data"
SNOTEL_START = "1979-10-01"

# NWS forecast point (same as the MapClick link)
NWS_GRID = "https://api.weather.gov/gridpoints/SEW/145,31"
NWS_PAGE = ("https://forecast.weather.gov/MapClick.php?lat=46.92912043955674"
            "&lon=-121.50098133017309&site=sew&unit=0&lg=en&FcstType=text")

# NWAC avalanche zone covering Crystal
AVY_ZONE_ID = 3023
AVY_ZONE_NAME = "West Slopes South"
AVY_PRODUCT_API = "https://api.avalanche.org/v2/public/product"
AVY_PAGE = "https://nwac.us/forecasts/avalanche/west-slopes-south"

# Outlook thresholds (judgment calls - tune to taste)
FRESH_24H_IN = 6
FRESH_72H_IN = 12
RAIN_SNOW_LEVEL_FT = 5000
WIND_HOLD_GUST_MPH = 40

# Forecast snowfall chart: top of the scale (inches per 6 hours). Grows automatically for bigger storms.
FORECAST_SNOW_SCALE_IN = 2
