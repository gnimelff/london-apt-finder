"""
Enrichment pipeline — runs all enrichment steps for a single listing.

lat/lng priority:
  1. Already on the listing from the scraper (Rightmove, OTM, OpenRent all provide it)
  2. Derived from postcode via postcodes.io (fallback only)

This saves geocoding API calls for the majority of listings.
"""
import re
import logging
from enrichment.geocode import postcode_to_latlon, postcode_to_borough
from enrichment.tfl import commute_minutes
from enrichment.cycling import cycling_commute

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Floor / basement detection — no API calls, pure text analysis
# ---------------------------------------------------------------------------
_BASEMENT_RE = re.compile(
    r"\b(basement|lower ground|lower-ground|below ground|lg floor)\b", re.I
)
_FLOOR_MAP = {
    "lower ground": -1, "basement": -1,
    "ground": 0,
    "first": 1, "1st": 1,
    "second": 2, "2nd": 2,
    "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4,
    "fifth": 5, "5th": 5,
    "sixth": 6, "6th": 6,
    "top": 99,  # sentinel for "top floor"
}
_FLOOR_RE = re.compile(
    r"\b(lower ground|basement|ground|top|first|second|third|fourth|fifth|sixth"
    r"|1st|2nd|3rd|4th|5th|6th)\s+floor\b",
    re.I,
)


def _extract_floor_info(listing: dict) -> None:
    """Set is_basement (bool) and floor_number (int|None) on listing in-place."""
    combined = " ".join([
        str(listing.get("address", "")),
        str(listing.get("description", "")),
    ])
    is_basement = bool(_BASEMENT_RE.search(combined))
    floor_number = None
    m = _FLOOR_RE.search(combined)
    if m:
        key = m.group(1).lower()
        floor_number = _FLOOR_MAP.get(key)
        if key in ("lower ground", "basement"):
            is_basement = True
    listing["is_basement"] = is_basement
    listing["floor_number"] = floor_number


def enrich(listing: dict) -> dict:
    """Mutate listing in-place with enrichment fields. Returns it."""

    # 1. Coordinates — use scraper-provided ones if available
    lat = listing.get("lat")
    lng = listing.get("lng")

    if not (lat and lng):
        postcode = listing.get("postcode")
        if postcode:
            coords = postcode_to_latlon(postcode)
            if coords:
                lat, lng = coords
                listing["lat"] = lat
                listing["lng"] = lng
                log.debug("Geocoded %s → (%s, %s)", postcode, lat, lng)
            else:
                log.debug("No coords for %s (postcode=%s)", listing.get("listing_id"), postcode)
        else:
            log.debug("No postcode or coords for listing %s", listing.get("listing_id"))

    # 2. TfL commute time + cycling time
    if lat and lng:
        listing["commute_mins"] = commute_minutes(lat, lng)
        cycling_mins, cycling_km = cycling_commute(lat, lng)
        listing["cycling_mins"] = cycling_mins
        listing["cycling_km"] = cycling_km
    else:
        listing["commute_mins"] = None
        listing["cycling_mins"] = None
        listing["cycling_km"] = None

    # 3. Borough from postcode (full postcode only)
    listing["borough"] = postcode_to_borough(listing.get("postcode"))

    # 4. Floor level / basement detection (text-only, no API)
    _extract_floor_info(listing)

    return listing
