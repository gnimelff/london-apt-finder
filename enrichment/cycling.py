"""
Google Maps Distance Matrix API — cycling time and distance to destination.

Returns (duration_mins, distance_km) or (None, None) on failure.
"""
import logging
import httpx
from config import GOOGLE_MAPS_API_KEY

log = logging.getLogger(__name__)

DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

# WeWork Waterloo destination
DEST_LAT = 51.5074
DEST_LNG = -0.1278


def cycling_commute(lat: float, lng: float) -> tuple[int | None, float | None]:
    """Return (cycling_mins, cycling_km) to Waterloo, or (None, None) on failure."""
    if not GOOGLE_MAPS_API_KEY or not lat or not lng:
        return None, None

    try:
        resp = httpx.get(
            DISTANCE_MATRIX_URL,
            params={
                "origins": f"{lat},{lng}",
                "destinations": f"{DEST_LAT},{DEST_LNG}",
                "mode": "bicycling",
                "key": GOOGLE_MAPS_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "OK":
            log.warning("Google Maps status: %s", data.get("status"))
            return None, None

        element = data["rows"][0]["elements"][0]
        if element.get("status") != "OK":
            log.warning("Google Maps element status: %s", element.get("status"))
            return None, None

        duration_secs = element["duration"]["value"]
        distance_metres = element["distance"]["value"]

        duration_mins = round(duration_secs / 60)
        distance_km = round(distance_metres / 1000, 1)

        return duration_mins, distance_km

    except Exception as e:
        log.warning("Cycling lookup failed for (%s, %s): %s", lat, lng, e)
        return None, None
