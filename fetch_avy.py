"""Pull the current NWAC avalanche product for West Slopes South into data/avalanche_latest.json."""
import json
from datetime import datetime

import requests

import config
import status

OUT = config.DATA / "avalanche_latest.json"


def main():
    config.DATA.mkdir(exist_ok=True)
    params = {"type": "forecast", "center_id": "NWAC", "zone_id": config.AVY_ZONE_ID}
    r = requests.get(config.AVY_PRODUCT_API, params=params, headers={"User-Agent": config.USER_AGENT},
                     timeout=config.TIMEOUT)
    r.raise_for_status()
    p = r.json()
    out = {
        "fetched": datetime.now().isoformat(timespec="minutes"),
        "product_type": p.get("product_type"),  # "forecast" in season, "summary" off-season
        "published": p.get("published_time"),
        "expires": p.get("expires_time"),
        "danger": p.get("danger") or [],  # ratings only: NWAC's written forecast stays on their site
    }
    OUT.write_text(json.dumps(out, indent=1))
    status.mark("avalanche")
    print(f"Avalanche: {out['product_type']} published {out['published']}, valid until {out['expires']}")


if __name__ == "__main__":
    main()
