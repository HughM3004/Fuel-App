"""
Fetch UK Fuel Finder prices and forecourt details, and write a compact
site/data.json for the map page.

Runs in GitHub Actions every 30 minutes. Credentials come from the
FUEL_FINDER_CLIENT_ID and FUEL_FINDER_CLIENT_SECRET repository secrets and
never reach the web page.

Optional settings (set in the workflow file):
  CENTRE_LAT, CENTRE_LON   centre of the area to keep (default: Bedford)
  REGION_RADIUS_MILES      how far out to keep stations; 0 = whole UK
"""

import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import requests

BASE = "https://www.fuel-finder.service.gov.uk/api/v1"
BATCH_SIZE = 500
TIMEOUT = 60
FUELS = ("E10", "E5", "B7_STANDARD", "B7_PREMIUM")

CENTRE_LAT = float(os.getenv("CENTRE_LAT", "52.1360"))
CENTRE_LON = float(os.getenv("CENTRE_LON", "-0.4667"))
RADIUS_MILES = float(os.getenv("REGION_RADIUS_MILES", "40"))


def log(msg):
    print(msg, flush=True)


def miles_between(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def unwrap(body):
    """The API has returned both bare lists and {"data": ...} wrappers."""
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def get_token(client_id, client_secret):
    resp = requests.post(
        f"{BASE}/oauth/generate_access_token",
        json={"client_id": client_id, "client_secret": client_secret},
        timeout=TIMEOUT,
    )
    if resp.status_code == 401:
        sys.exit("Fuel Finder rejected the client ID or secret. Check the repository secrets.")
    resp.raise_for_status()
    return unwrap(resp.json())["access_token"]


def get_json(path, token, params, attempts=4):
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(
                f"{BASE}{path}",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=TIMEOUT,
            )
            if resp.status_code == 404:
                return None  # past the last batch
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 10))
                log(f"  rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return unwrap(resp.json())
        except requests.RequestException as err:
            if attempt == attempts:
                raise
            log(f"  {path} batch {params.get('batch-number')} failed ({err}); retrying")
            time.sleep(5 * attempt)
    return None


def get_all(path, token):
    rows, batch = [], 1
    while True:
        page = get_json(path, token, {"batch-number": batch})
        if not page:
            break
        rows.extend(page)
        log(f"  {path}: batch {batch}, {len(page)} records")
        if len(page) < BATCH_SIZE:
            break
        batch += 1
    return rows


def clean_price(raw):
    """Prices arrive as strings like '0142.9000' (pence). Reject obvious errors."""
    if raw in (None, ""):
        return None
    try:
        p = float(raw)
    except (TypeError, ValueError):
        return None
    if 0.5 < p < 5:  # submitted in pounds by mistake
        p *= 100
    if not 80 <= p <= 300:
        return None
    return round(p, 1)


def address_of(info):
    loc = info.get("location") or {}
    addr = info.get("address") or {}
    line1 = loc.get("address_line_1") or addr.get("address_line_1") or addr.get("line1") or ""
    city = loc.get("city") or addr.get("city") or ""
    postcode = loc.get("postcode") or addr.get("postcode") or ""
    street = ", ".join(x.strip().title() for x in (line1, city) if x and x.strip())
    return street, postcode.strip().upper()


def main():
    cid = os.getenv("FUEL_FINDER_CLIENT_ID")
    secret = os.getenv("FUEL_FINDER_CLIENT_SECRET")
    if not cid or not secret:
        sys.exit("Set FUEL_FINDER_CLIENT_ID and FUEL_FINDER_CLIENT_SECRET.")

    log("Getting access token")
    token = get_token(cid, secret)

    log("Fetching forecourt details")
    infos = {r["node_id"]: r for r in get_all("/pfs", token)}
    log("Fetching prices")
    prices = get_all("/pfs/fuel-prices", token)

    stations = []
    for row in prices:
        info = infos.get(row.get("node_id"))
        if not info or info.get("permanent_closure"):
            continue
        loc = info.get("location") or {}
        try:
            lat, lon = float(loc["latitude"]), float(loc["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if RADIUS_MILES > 0 and miles_between(CENTRE_LAT, CENTRE_LON, lat, lon) > RADIUS_MILES:
            continue

        fuel_prices = {}
        for fp in row.get("fuel_prices") or []:
            code = fp.get("fuel_type")
            price = clean_price(fp.get("price"))
            if code in FUELS and price:
                updated = fp.get("price_change_effective_timestamp") or fp.get("price_last_updated")
                fuel_prices[code] = [price, updated]
        if not fuel_prices:
            continue

        street, postcode = address_of(info)
        name = info.get("trading_name") or row.get("trading_name") or "Petrol station"
        stations.append({
            "id": row["node_id"],
            "name": name.strip().title() if name.isupper() else name.strip(),
            "brand": (info.get("brand_name") or "").strip().title(),
            "addr": street,
            "pc": postcode,
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "p": fuel_prices,
            "mw": bool(info.get("is_motorway_service_station")),
            "closed": bool(info.get("temporary_closure")),
        })

    if not stations:
        sys.exit("No stations came back. Leaving the previous data in place.")

    out = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "centre": [CENTRE_LAT, CENTRE_LON],
        "radius_miles": RADIUS_MILES,
        "stations": stations,
    }
    os.makedirs("site", exist_ok=True)
    with open("site/data.json", "w") as f:
        json.dump(out, f, separators=(",", ":"))
    log(f"Wrote {len(stations)} stations to site/data.json")


if __name__ == "__main__":
    main()
