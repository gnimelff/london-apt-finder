"""
Rightmove scraper — UK's largest portal.

How it works (verified against live site):
  - Data is in <script id="__NEXT_DATA__"> JSON
  - Key path: props.pageProps.searchResults.properties
  - lat/lng available directly in location.latitude / location.longitude
  - propertyUrl is relative (/properties/12345) — prepend rightmove.co.uk
  - Must use full pre-encoded URL to avoid double-encoding REGION^87490

IMPORTANT: pass the full URL string directly; do NOT use httpx params dict
for locationIdentifier or it double-encodes the ^ character.
"""
import re
import json
import logging
from scrapers.base import fetch, polite_delay

log = logging.getLogger(__name__)

BASE_SEARCH = (
    "https://www.rightmove.co.uk/property-to-rent/find.html"
    "?locationIdentifier=REGION%5E87490"
    "&propertyTypes=flat"
    "&includeLetAgreed=false"
    "&dontShow=houseShare%2Cretirement"
    "&minBedrooms={min_beds}"
    "&maxPrice={max_price}"
    "&index={index}"
)


def scrape(max_price: int = 3200, min_beds: int = 1, max_pages: int = 3) -> list[dict]:
    listings = []
    page_size = 25  # Rightmove returns 25 per page

    for page in range(max_pages):
        index = page * page_size
        url = BASE_SEARCH.format(min_beds=min_beds, max_price=max_price, index=index)

        try:
            resp = fetch(url)
        except Exception as e:
            log.warning("Rightmove page %d failed: %s", page, e)
            break

        data = _extract_next_data(resp.text)
        if not data:
            log.warning("Rightmove: no __NEXT_DATA__ on page %d", page)
            break

        try:
            props = data["props"]["pageProps"]["searchResults"]["properties"]
        except (KeyError, TypeError) as e:
            log.warning("Rightmove: unexpected structure on page %d: %s", page, e)
            break

        if not props:
            break

        for p in props:
            try:
                pid = str(p["id"])
                address = p.get("displayAddress", "")
                price_info = p.get("price", {})
                price = None
                if isinstance(price_info, dict):
                    # Prefer the pre-calculated pcm from displayPrices (avoids weekly conversion errors)
                    display_prices = price_info.get("displayPrices", [])
                    pcm_entry = next((d for d in display_prices if "pcm" in d.get("displayPrice", "")), None)
                    if pcm_entry:
                        m = re.search(r"[\d,]+", pcm_entry["displayPrice"].replace(",", ""))
                        price = int(m.group()) if m else None
                    else:
                        # Fallback: convert from amount using frequency
                        amount = price_info.get("amount")
                        frequency = price_info.get("frequency", "monthly")
                        if amount:
                            price = round(amount * 52 / 12) if frequency == "weekly" else amount
                beds = p.get("bedrooms", 0)
                loc = p.get("location", {})
                lat = loc.get("latitude") if isinstance(loc, dict) else None
                lng = loc.get("longitude") if isinstance(loc, dict) else None
                prop_url = p.get("propertyUrl", f"/properties/{pid}")

                # Combine summary + key features so Claude sees everything
                summary = p.get("summary", "")
                key_features = p.get("keyFeatures", []) or []
                description = summary
                if key_features:
                    description = summary + " | " + " | ".join(key_features)

                listings.append({
                    "site": "rightmove",
                    "listing_id": pid,
                    "url": f"https://www.rightmove.co.uk{prop_url}",
                    "address": address,
                    "postcode": _extract_postcode(address),
                    "price_pcm": price,
                    "bedrooms": beds,
                    "furnished": _parse_furnished(p),
                    "lat": lat,
                    "lng": lng,
                    "description": description,
                })
            except Exception as e:
                log.debug("Rightmove property parse error: %s", e)

        log.info("Rightmove page %d: %d listings (total so far: %d)", page, len(props), len(listings))
        polite_delay(3, 6)

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


def _parse_furnished(prop: dict) -> bool | None:
    key_features = prop.get("keyFeatures", []) or []
    text = " ".join([
        str(prop.get("summary", "")),
        str(prop.get("displayStatus", "")),
        " ".join(key_features),
    ]).lower()
    if "unfurnished" in text:
        return False
    if "furnished" in text:  # catches "furnished", "part furnished", "fully furnished"
        return True
    return None


def _extract_postcode(text: str) -> str | None:
    m = re.search(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b", text.upper())
    return m.group(1).upper() if m else None
