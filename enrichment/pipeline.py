"""
Enrichment pipeline — runs all enrichment steps for a single listing.

lat/lng priority:
  1. Already on the listing from the scraper (Rightmove, OTM, OpenRent all provide it)
  2. Derived from postcode via postcodes.io (fallback only)

This saves geocoding API calls for the majority of listings.
"""
import logging
from enrichment.geocode import postcode_to_latlon
from enrichment.tfl import commute_minutes
from enrichment.crime import crime_count_nearby
from enrichment.epc import epc_rating
from enrichment.cycling import cycling_commute

log = logging.getLogger(__name__)


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
        listing["crime_count"] = crime_count_nearby(lat, lng)
        cycling_mins, cycling_km = cycling_commute(lat, lng)
        listing["cycling_mins"] = cycling_mins
        listing["cycling_km"] = cycling_km
    else:
        listing["commute_mins"] = None
        listing["crime_count"] = None
        listing["cycling_mins"] = None
        listing["cycling_km"] = None

    # 3. EPC rating (needs postcode)
    postcode = listing.get("postcode")
    listing["epc_rating"] = epc_rating(postcode) if postcode else None

    return listing
