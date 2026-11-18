# Crystal Mountain Ski Conditions

A personal dashboard that combines snow history, the weather forecast, and avalanche information for Crystal Mountain, WA. It refreshes 6 times a day: 5 AM, 8 AM, 11 AM, 2 PM, 5 PM and 8 PM Pacific.

## How refreshes are triggered

- **Main trigger: [cron-job.org](https://cron-job.org).** A job there calls GitHub's API to start the `Refresh dashboard` workflow at the six times above (Pacific time zone, so daylight saving is handled). It uses a fine-grained GitHub token limited to this repository with only "Actions: read and write" permission. **The token expires; renew it in GitHub settings and paste the new one into the cron-job.org job before then.**
- **No backup schedule.** GitHub's own schedule was removed in Nov 2026: it ran only about 3 times a day, often hours late. If cron-job.org stops (outage, expired token), the page stops updating; a refresh can still be started by hand from the repo's Actions tab ("Refresh dashboard" → "Run workflow").

**Not official.** This project isn't affiliated with Crystal Mountain, NWAC, NWS, or NRCS. Always read the [NWAC avalanche forecast](https://nwac.us/forecasts/avalanche/west-slopes-south) before traveling in avalanche terrain.

## Data sources

- [Northwest Avalanche Center](https://nwac.us): Crystal Green Valley weather station and avalanche forecasts
- [National Weather Service](https://www.weather.gov): point forecast
- [NRCS SNOTEL](https://www.nrcs.usda.gov/resources/data-and-reports/snow-and-water-interactive-map): Corral Pass station

All NWAC content belongs to the Northwest Avalanche Center.
