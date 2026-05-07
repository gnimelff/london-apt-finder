"""
postcodes.io — free, no API key, converts UK postcodes to lat/lng.

Handles both full postcodes (SW2 1JF) and outward codes / districts (SW2, SE15, WC2N).
Full postcodes are tried first; if that 404s, falls back to the outcode endpoint
which returns the centroid of the district — good enough for commute estimation.
"""
import re
import logging
import httpx

log = logging.getLogger(__name__)

_FULL_POSTCODE_RE = re.compile(
    r"^[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}$", re.IGNORECASE
)


def postcode_to_latlon(postcode: str) -> tuple[float, float] | None:
    if not postcode:
        return None
    clean = postcode.strip().upper()

    # Try full postcode first
    if _FULL_POSTCODE_RE.match(clean):
        result = _lookup_full(clean.replace(" ", ""))
        if result:
            return result

    # Fall back to outcode (district) lookup — e.g. SE15, WC2N, SW2
    outcode = clean.split()[0] if " " in clean else clean
    # Strip trailing sector digit+letters if present to get outcode
    m = re.match(r"^([A-Z]{1,2}\d{1,2}[A-Z]?)", outcode)
    if m:
        return _lookup_outcode(m.group(1))

    return None


def postcode_to_borough(postcode: str) -> str | None:
    """Return the London borough (admin_district) for a full postcode, or None."""
    if not postcode:
        return None
    clean = postcode.strip().upper().replace(" ", "")
    if not _FULL_POSTCODE_RE.match(clean):
        return None
    try:
        resp = httpx.get(
            f"https://api.postcodes.io/postcodes/{clean}",
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("result", {}).get("admin_district") or None
    except Exception as e:
        log.debug("borough lookup failed for %s: %s", clean, e)
    return None


def _lookup_full(postcode_no_space: str) -> tuple[float, float] | None:
    try:
        resp = httpx.get(
            f"https://api.postcodes.io/postcodes/{postcode_no_space}",
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json().get("result", {})
        lat, lng = result.get("latitude"), result.get("longitude")
        if lat and lng:
            return (float(lat), float(lng))
    except Exception as e:
        log.debug("full postcode lookup failed for %s: %s", postcode_no_space, e)
    return None


def _lookup_outcode(outcode: str) -> tuple[float, float] | None:
    try:
        resp = httpx.get(
            f"https://api.postcodes.io/outcodes/{outcode}",
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json().get("result", {})
        lat, lng = result.get("latitude"), result.get("longitude")
        if lat and lng:
            log.debug("outcode fallback: %s → (%s, %s)", outcode, lat, lng)
            return (float(lat), float(lng))
    except Exception as e:
        log.warning("outcode lookup failed for %s: %s", outcode, e)
    return None
