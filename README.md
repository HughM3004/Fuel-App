# Fuel near me

A small web app that shows fuel prices near you, ranked by what a fill-up actually costs once the detour is counted. Prices come from the government Fuel Finder service; the map is OpenStreetMap.

## How it works

- Every 30 minutes, GitHub runs `fetch_prices.py`. It logs in to Fuel Finder with your credentials, downloads prices and forecourt details, keeps the stations within 40 miles of Bedford, and saves them as `data.json`.
- GitHub Pages then publishes the `site` folder (the map page plus that data file) at a web address you can share.
- Your Fuel Finder secret is stored in GitHub and never appears on the web page. The price data itself is public government data, so it doesn't need protecting.

There is no server to maintain, and it costs nothing.

## Setting it up (about 30 minutes)

**1. Get Fuel Finder credentials.**
Go to https://www.developer.fuel-finder.service.gov.uk, sign in with GOV.UK One Login, and register for API access. Make a note of the **client ID** and **client secret** for the live (production) service.

**2. Create a GitHub repository.**
Sign up at https://github.com if you haven't already. Create a new **public** repository (for example `fuel-prices`). Public is needed for free GitHub Pages. Only the code is visible; your secret is not.

**3. Upload the files, keeping the folders:**

```
fetch_prices.py
README.md
.github/workflows/update.yml
site/index.html
site/manifest.json
site/icon.svg
```

The `.github` folder is hidden on Macs and often gets skipped by drag and drop. The easy way round it: in the repository, choose **Add file → Create new file**, type `.github/workflows/update.yml` as the name, and paste the contents in.

**4. Add your credentials as secrets.**
In the repository, go to **Settings → Secrets and variables → Actions → New repository secret**. Add two:

- `FUEL_FINDER_CLIENT_ID`
- `FUEL_FINDER_CLIENT_SECRET`

**5. Switch on Pages.**
Go to **Settings → Pages**, and under **Source** choose **GitHub Actions**.

**6. Run it for the first time.**
Go to the **Actions** tab, choose **Update fuel prices**, then **Run workflow**. After a couple of minutes the app is live at:

`https://YOUR-USERNAME.github.io/fuel-prices/`

If the run fails, click into it. The log says in plain terms what went wrong (usually a mistyped secret).

**7. Share it.**
Send the link. On a phone, open it and choose **Add to Home Screen** so it opens like an app. The first time, the phone asks permission to use your location.

## Changing things

- **Area covered:** edit `CENTRE_LAT`, `CENTRE_LON` and `REGION_RADIUS_MILES` in `.github/workflows/update.yml`. Set the radius to `0` for the whole UK. The data file then grows to about 1–2 MB, which is still fine on a phone.
- **Fill-up size and mpg:** each person sets their own under "Your car and location" in the app. It is remembered on their phone.

## Things to know

- **Timing.** GitHub's timer can run 5–15 minutes late at busy times, so prices are typically up to an hour old. Fuel Finder itself allows stations 30 minutes to report a change.
- **The 60-day rule.** GitHub pauses scheduled jobs in a repository that has had no activity for 60 days. It emails you first, and re-enabling is one click in the Actions tab. If the data does go stale, the app shows a warning once prices are more than three hours old, so nobody is silently misled.
- **Bad prices.** Occasionally a station submits a price in pounds instead of pence, or a typo. The script corrects the pounds case and drops anything outside 80p–300p. Prices over a week old are marked in the list.
- **Detour cost.** This is an estimate: straight-line distance × 1.3 for roads, there and back, at the car's mpg. It is good enough to tell you whether 3p a litre is worth 8 miles; it isn't a sat-nav.
- **Map tiles.** OpenStreetMap's free tiles are fine for a handful of users. If this ever spread to hundreds of people, you would need a paid tile provider.
