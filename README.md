# Crystal Mountain Ski Conditions

A personal dashboard that combines snow history, the weather forecast, and avalanche information for Crystal Mountain, WA. It refreshes 6 times a day: 5 AM, 8 AM, 11 AM, 2 PM, 5 PM and 8 PM Pacific.

## How refreshes are triggered

- **Main trigger: [cron-job.org](https://cron-job.org).** A job there calls GitHub's API to start the `Refresh dashboard` workflow at the six times above (Pacific time zone, so daylight saving is handled). It uses a fine-grained GitHub token limited to this repository with only "Actions: read and write" permission. **The token expires; renew it in GitHub settings and paste the new one into the cron-job.org job before then.**
- **Backup: GitHub's own schedule** (`.github/workflows/refresh.yml`), hourly. GitHub runs only about 3 of these a day and often hours late, which is why the outside trigger exists.

**Not official.** This project isn't affiliated with Crystal Mountain, NWAC, NWS, or NRCS. Always read the [NWAC avalanche forecast](https://nwac.us/forecasts/avalanche/west-slopes-south) before traveling in avalanche terrain.

## Data sources

- [Northwest Avalanche Center](https://nwac.us): Crystal Green Valley weather station and avalanche forecasts
- [National Weather Service](https://www.weather.gov): point forecast
- [NRCS SNOTEL](https://www.nrcs.usda.gov/resources/data-and-reports/snow-and-water-interactive-map): Corral Pass station

All NWAC content belongs to the Northwest Avalanche Center.
