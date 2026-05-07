"""
TfL Journey Planner — cycling time and distance to destination.

Uses mode=cycle (direct cycling, no bike hire) with cyclePreference=fastestRoute.
Returns (duration_mins, distance_km) or (None, None) on failure.
"""
import logging
import httpx
from config import TFL_API_KEY

log = logging.getLogger(__name__)

JOURNEY_URL = "https://api.tfl.gov.uk/Journey/JourneyResults/{origin}/to/{destination}"

# WeWork Waterloo destination
DEST_LAT = 51.5074
DEST_LNG = -0.1278


def cycling_commute(lat: float, lng: float) -> tuple[int | None, float | None]:
    """Return (cycling_mins, cycling_km) to Waterloo via fastest cycle route, or (None, None)."""
    if not lat or not lng:
        return None, None

    origin = f"{lat},{lng}"
    destination = f"{DEST_LAT},{DEST_LNG}"
    url = JOURNEY_URL.format(origin=origin, destination=destination)

    try:
        resp = httpx.get(
            url,
            params={
                "app_key": TFL_API_KEY,
                "mode": "cycle",
                "journeyPreference": "LeastTime",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        journeys = data.get("journeys", [])
        if not journeys:
            return None, None

        # Take the fastest journey by duration
        fastest = min(journeys, key=lambda j: j.get("duration", 9999))
        duration_mins = fastest.get("duration")

        # Sum leg distances (metres) to get total km
        legs = fastest.get("legs", [])
        total_m = sum(leg.get("distance", 0) for leg in legs)
        distance_km = round(total_m / 1000, 1) if total_m else None

        return duration_mins, distance_km

    except Exception as e:
        log.warning("TfL cycling lookup failed for (%s, %s): %s", lat, lng, e)
        return None, None
