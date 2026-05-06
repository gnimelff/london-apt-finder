"""
EPC (Energy Performance Certificate) — new GOV.UK service.

API base: https://api.get-energy-performance-data.communities.gov.uk
Auth:     Bearer token (register at https://get-energy-performance-data.communities.gov.uk)
Field:    currentEnergyEfficiencyBand  (A–G)

The old epc.opendatacommunities.org service is retired as of May 2026.
"""
import logging
import httpx
from config import EPC_API_KEY

log = logging.getLogger(__name__)

EPC_URL = "https://api.get-energy-performance-data.communities.gov.uk/api/domestic/search"


_FULL_POSTCODE_RE = __import__('re').compile(
    r"^[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}$", __import__('re').IGNORECASE
)


def epc_rating(postcode: str) -> str | None:
    """Return the most recent EPC band (A-G) for the given postcode, or None.
    EPC API requires a full postcode — skips partial/outward-only codes."""
    if not postcode or not EPC_API_KEY:
        return None
    if not _FULL_POSTCODE_RE.match(postcode.strip()):
        return None  # partial postcode — EPC lookup not possible

    try:
        resp = httpx.get(
            EPC_URL,
            params={"postcode": postcode, "page_size": 5},
            headers={
                "Authorization": f"Bearer {EPC_API_KEY}",
                "Accept": "application/json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        rows = resp.json().get("data", [])
        if not rows:
            return None
        # Return the most recently registered certificate's band
        rows_sorted = sorted(rows, key=lambda r: r.get("registrationDate", ""), reverse=True)
        return rows_sorted[0].get("currentEnergyEfficiencyBand")
    except Exception as e:
        log.warning("EPC lookup failed for %s: %s", postcode, e)
        return None
