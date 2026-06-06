"""
TfL Unified API — journey planner for door-to-door commute time.
Register free at https://api-portal.tfl.gov.uk/ to get an app_key.
500 requests/day on the free plan.
"""
import logging
import httpx
from config import TFL_API_KEY, DEST_LAT, DEST_LNG

log = logging.getLogger(__name__)

JOURNEY_URL = "https://api.tfl.gov.uk/Journey/JourneyResults/{origin}/to/{destination}"

# Destination loaded from DEST_LAT / DEST_LNG env vars (set in GitHub secrets)


def commute_minutes(lat: float, lng: float) -> int | None:
    """Return fastest TfL door-to-door journey time in minutes, arriving 09:00."""
    origin = f"{lat},{lng}"
    destination = f"{DEST_LAT},{DEST_LNG}"
    url = JOURNEY_URL.format(origin=origin, destination=destination)

    try:
        resp = httpx.get(
            url,
            params={
                "app_key": TFL_API_KEY,
                "mode": "tube,dlr,overground,elizabeth-line,national-rail,walking",
                "timeIs": "Arriving",
                "time": "0900",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        journeys = data.get("journeys", [])
        if not journeys:
            return None

        # Take the fastest journey
        durations = [j.get("duration") for j in journeys if j.get("duration")]
        return min(durations) if durations else None

    except Exception as e:
        log.warning("TfL journey failed for (%s, %s): %s", lat, lng, e)
        return None
