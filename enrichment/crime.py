"""
data.police.uk — official UK Police open data API.
No API key required. Returns crime incident count within ~500m radius.
We query the last 2 months and average to smooth seasonal variation.
"""
import logging
from datetime import date, timedelta
import httpx

log = logging.getLogger(__name__)

CRIMES_URL = "https://data.police.uk/api/crimes-street/all-crime"


def crime_count_nearby(lat: float, lng: float, months: int = 2) -> int | None:
    """Return average monthly crime incidents within ~500m of the given coordinates."""
    total = 0
    fetched = 0

    today = date.today()
    for i in range(months):
        # Go back i+1 months (API has ~2 month lag)
        d = today.replace(day=1) - timedelta(days=30 * (i + 1))
        date_str = d.strftime("%Y-%m")
        try:
            resp = httpx.get(
                CRIMES_URL,
                params={"lat": lat, "lng": lng, "date": date_str},
                timeout=20,
            )
            resp.raise_for_status()
            crimes = resp.json()
            total += len(crimes)
            fetched += 1
        except Exception as e:
            log.warning("Crime API failed for %s/%s at %s: %s", lat, lng, date_str, e)

    if fetched == 0:
        return None
    return round(total / fetched)
