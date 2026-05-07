"""
OpenRent scraper — direct landlord listings, no agency fees.

How it works (verified against live site):
  1. Fetch the search page — the HTML embeds parallel JS arrays containing ALL
     property data: PROPERTYIDS, prices, bedrooms, latitudes, longitudes, etc.
  2. Parse those arrays directly from the <script> block (no lazy-loading needed).
  3. Filter cheaply by price/bedrooms/studio in Python before any API call.
  4. Batch-call /search/propertiesbyid (repeated ids= params, max 20/request)
     to get address titles and descriptions for the survivors.
"""
import re
import json
import logging
import httpx
from scrapers.base import fetch, polite_delay

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.openrent.co.uk/properties-to-rent/london"
DETAILS_URL = "https://www.openrent.co.uk/search/propertiesbyid"
BATCH_SIZE = 20


def scrape(max_price: int = 3200, min_price: int = 2000, min_beds: int = 1, max_results: int = 150) -> list[dict]:
    params = {
        "term": "London",
        "area": 8,
        "bedrooms_min": min_beds,
        "prices_min": min_price,
        "prices_max": max_price,
    }
    try:
        resp = fetch(SEARCH_URL, params=params)
    except Exception as e:
        log.error("OpenRent search page failed: %s", e)
        raise  # propagate so run.py can send a Telegram alert

    arrays = _extract_arrays(resp.text)
    if not arrays or not arrays.get("PROPERTYIDS"):
        log.warning("OpenRent: could not extract property arrays from page")
        return []

    ids = arrays["PROPERTYIDS"]
    prices = arrays.get("prices", [])
    bedrooms = arrays.get("bedrooms", [])
    lats = arrays.get("PROPERTYLISTLATITUDES", [])
    lngs = arrays.get("PROPERTYLISTLONGITUDES", [])
    furnished_arr = arrays.get("furnished", [])
    is_studio = arrays.get("isstudio", [])
    is_shared = arrays.get("isshared", [])
    is_live = arrays.get("islivelistBool", [])

    log.info("OpenRent: %d total properties in page", len(ids))

    # Pre-filter in Python (avoids wasting API calls on propertiesbyid)
    candidates = []
    for i, pid in enumerate(ids):
        def _get(arr, idx, default=None):
            return arr[idx] if idx < len(arr) else default

        if not _get(is_live, i, 1):
            continue
        price = _get(prices, i)
        beds = _get(bedrooms, i)
        studio = _get(is_studio, i, 0)
        shared = _get(is_shared, i, 0)
        if price and price > max_price:
            continue
        if beds is not None and beds < min_beds:
            continue
        if studio:
            continue
        if shared:
            continue
        candidates.append({
            "idx": i,
            "listing_id": pid,
            "price_pcm": price,
            "bedrooms": beds,
            "lat": _get(lats, i),
            "lng": _get(lngs, i),
            "furnished": bool(_get(furnished_arr, i)),
        })

    log.info("OpenRent: %d after pre-filter", len(candidates))

    # Cap to avoid processing thousands of listings in one run
    if len(candidates) > max_results:
        candidates = candidates[:max_results]
        log.info("OpenRent: capped to %d candidates", max_results)

    # Fetch details in batches
    results = []
    for batch_start in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[batch_start: batch_start + BATCH_SIZE]
        batch_ids = [c["listing_id"] for c in batch]
        details = _fetch_details(batch_ids)

        details_by_id = {d["id"]: d for d in details}
        for c in batch:
            detail = details_by_id.get(c["listing_id"], {})
            title = detail.get("title", "")
            results.append({
                "site": "openrent",
                "listing_id": str(c["listing_id"]),
                "url": f"https://www.openrent.co.uk/{c['listing_id']}",
                "address": title,
                "postcode": _extract_postcode(title),
                "price_pcm": c["price_pcm"],
                "bedrooms": c["bedrooms"],
                "furnished": c["furnished"],
                "lat": c["lat"],
                "lng": c["lng"],
                "description": detail.get("description", ""),
            })
        polite_delay(1, 3)

    log.info("OpenRent: returning %d listings", len(results))
    return results


def _fetch_details(ids: list) -> list[dict]:
    """Call /search/propertiesbyid with repeated ids= params."""
    url = DETAILS_URL + "?" + "&".join(f"ids={i}" for i in ids)
    headers_extra = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": SEARCH_URL,
    }
    try:
        resp = fetch(url, extra_headers=headers_extra)
        return resp.json()
    except Exception as e:
        log.warning("OpenRent propertiesbyid failed: %s", e)
        return []


def _extract_arrays(html: str) -> dict:
    """Extract parallel data arrays from OpenRent's large inline script block."""
    arrays = {}
    # Numeric arrays
    for name in ["islivelistBool", "prices", "bedrooms", "bathrooms",
                 "furnished", "unfurnished", "isstudio", "isshared",
                 "PROPERTYLISTLATITUDES", "PROPERTYLISTLONGITUDES"]:
        m = re.search(rf"var\s+{re.escape(name)}\s*=\s*\[([\d.,\s\-]+)\]", html)
        if m:
            try:
                arrays[name] = [float(x) if "." in x else int(x)
                                 for x in m.group(1).split(",") if x.strip()]
            except ValueError:
                pass

    # Property ID array
    m = re.search(r"var\s+PROPERTYIDS\s*=\s*\[([\d,\s]+)\]", html)
    if m:
        arrays["PROPERTYIDS"] = [int(x) for x in m.group(1).split(",") if x.strip()]

    return arrays


def _extract_postcode(text: str) -> str | None:
    m = re.search(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b", text.upper())
    if m:
        return m.group(1).upper()
    # Partial postcode from title like "SW17" or "SE15"
    m2 = re.search(r",\s*([A-Z]{1,2}\d{1,2}[A-Z]?)$", text.strip().upper())
    return m2.group(1) if m2 else None
