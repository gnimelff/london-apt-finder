"""
OnTheMarket scraper — agents often list here 24-72hrs before Rightmove/Zoopla.

How it works (verified against live site):
  - Data is in <script id="__NEXT_DATA__"> JSON (Redux initial state)
  - Key path: props.initialReduxState.results.list
  - lat/lng in location.lat / location.lon
  - price in "short-price" field (e.g. "£2,200") — parse the integer out
  - pagination via ?page=N query param
"""
import re
import json
import logging
from scrapers.base import fetch, polite_delay

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.onthemarket.com/to-rent/property/london/"


def scrape(max_price: int = 3200, min_beds: int = 1, max_pages: int = 3) -> list[dict]:
    listings = []

    for page in range(1, max_pages + 1):
        params = {
            "min-bedrooms": min_beds,
            "max-price": max_price,
            "page": page,
            "shared-accommodation": "false",
        }

        try:
            resp = fetch(SEARCH_URL, params=params)
        except Exception as e:
            log.warning("OnTheMarket page %d failed: %s", page, e)
            break

        data = _extract_next_data(resp.text)
        if not data:
            log.warning("OnTheMarket: no __NEXT_DATA__ on page %d", page)
            break

        try:
            props = data["props"]["initialReduxState"]["results"]["list"]
        except (KeyError, TypeError) as e:
            log.warning("OnTheMarket: unexpected structure on page %d: %s", page, e)
            break

        if not props:
            break

        for p in props:
            try:
                pid = str(p.get("id", ""))
                address = p.get("address", "")
                price = _parse_price(p.get("short-price", "") or p.get("price", ""))
                beds = p.get("bedrooms", 0)
                loc = p.get("location", {})
                lat = loc.get("lat") if isinstance(loc, dict) else None
                lng = loc.get("lon") if isinstance(loc, dict) else None
                detail_path = p.get("details-url", f"/details/{pid}/")

                listings.append({
                    "site": "otm",
                    "listing_id": pid,
                    "url": f"https://www.onthemarket.com{detail_path}",
                    "address": address,
                    "postcode": _extract_postcode(address),
                    "price_pcm": price,
                    "bedrooms": beds,
                    "furnished": _parse_furnished(p),
                    "lat": lat,
                    "lng": lng,
                    "description": " ".join(p.get("features", [])),
                })
            except Exception as e:
                log.debug("OTM property parse error: %s", e)

        log.info("OnTheMarket page %d: %d listings (total so far: %d)", page, len(props), len(listings))
        polite_delay(2, 5)

    return listings


def _extract_next_data(html: str) -> dict | None:
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html, re.DOTALL
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _parse_price(text: str) -> int | None:
    """Extract integer from strings like '£2,200' or '£2,200 pcm (£508 pw)'."""
    m = re.search(r"[\d,]+", text.replace(",", ""))
    return int(m.group()) if m else None


def _parse_furnished(prop: dict) -> bool | None:
    text = " ".join(str(f) for f in prop.get("features", [])).lower()
    if "unfurnished" in text:
        return False
    if "furnished" in text:
        return True
    return None


def _extract_postcode(text: str) -> str | None:
    m = re.search(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b", text.upper())
    if m:
        return m.group(1).upper()
    m2 = re.search(r",\s*([A-Z]{1,2}\d{1,2}[A-Z]?)$", text.strip().upper())
    return m2.group(1) if m2 else None
