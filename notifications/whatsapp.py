"""
WhatsApp notification via CallMeBot — free personal use.

Sends all high-scoring listings in a single batched message to avoid rate limiting.
If the combined message exceeds 3,500 chars it splits into chunks automatically.
"""
import time
import urllib.parse
import logging
import httpx
from config import CALLMEBOT_API_KEY, WHATSAPP_PHONE

log = logging.getLogger(__name__)

CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"
MAX_CHARS = 3500  # safe limit below WhatsApp's 4096 cap


def _format_listing(listing: dict) -> str:
    score = listing.get("score", "?")
    address = listing.get("address", "Unknown address")
    price = listing.get("price_pcm")
    price_str = f"£{price:,}/mo" if price else "price unknown"
    commute = listing.get("commute_mins")
    commute_str = f"{commute} min TfL" if commute else "TfL unknown"
    cycling_mins = listing.get("cycling_mins")
    cycling_km = listing.get("cycling_km")
    cycling_str = f"🚴 {cycling_mins} min ({cycling_km} km)" if cycling_mins and cycling_km else None
    epc = listing.get("epc_rating")
    epc_str = f"EPC {epc}" if epc else "EPC unknown"
    crime = listing.get("crime_count")
    crime_str = f"{crime} crimes/mo" if crime is not None else "crime N/A"
    area = listing.get("area_summary", "")
    url = listing.get("url", "")

    commute_line = commute_str
    if cycling_str:
        commute_line += f" | {cycling_str}"

    lines = [
        f"*Score {score}/10* — {listing.get('bedrooms', '?')}-bed",
        f"*{address}*",
        f"*{price_str}* | {commute_line} | {epc_str} | {crime_str}",
    ]
    if area:
        lines.append(area)
    if url:
        lines.append(url)

    return "\n".join(lines)


def _send_raw(text: str) -> bool:
    """Send a single WhatsApp message. Returns True on success."""
    encoded = urllib.parse.quote(text)
    url = f"{CALLMEBOT_URL}?phone={WHATSAPP_PHONE}&text={encoded}&apikey={CALLMEBOT_API_KEY}"
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        if 200 <= resp.status_code < 300:
            log.info("WhatsApp message sent (%d chars)", len(text))
            return True
        log.warning("CallMeBot returned %d: %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        log.error("WhatsApp send failed: %s", e)
        return False


def send_batch(listings: list[dict]) -> int:
    """
    Format all listings and send as one message (or chunked if too long).
    Returns the number of successfully sent chunks.
    """
    if not listings:
        return 0

    blocks = [_format_listing(l) for l in listings]
    divider = "\n---\n"
    header = f"🏠 *{len(listings)} new listing{'s' if len(listings) != 1 else ''}*\n---\n"

    # Build chunks that fit within MAX_CHARS
    chunks = []
    current_blocks = []
    current_len = len(header)

    for block in blocks:
        addition = (divider if current_blocks else "") + block
        if current_len + len(addition) > MAX_CHARS and current_blocks:
            chunks.append(header + divider.join(current_blocks))
            current_blocks = [block]
            current_len = len(header) + len(block)
        else:
            current_blocks.append(block)
            current_len += len(addition)

    if current_blocks:
        chunks.append(header + divider.join(current_blocks))

    sent = 0
    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(3)  # small gap between chunks to avoid rate limiting
        if _send_raw(chunk):
            sent += 1

    return sent


# Keep single-listing send for backwards compatibility
def send(listing: dict) -> bool:
    return send_batch([listing]) > 0
