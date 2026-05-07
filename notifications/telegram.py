"""
Telegram Bot notifications — free, reliable, no rate limits for personal use.

Setup (one-time):
  1. Message @BotFather on Telegram → /newbot → get your token
  2. Start a chat with your bot, then fetch:
     https://api.telegram.org/bot<TOKEN>/getUpdates
     to get your chat_id
  3. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS in .env / GitHub secrets
     TELEGRAM_CHAT_IDS is a comma-separated list for multiple recipients
"""
import time
import logging
import httpx
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS

log = logging.getLogger(__name__)

MAX_CHARS = 4000  # Telegram's limit is 4096


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


def _send_raw(chat_id: str, text: str) -> bool:
    """Send a single Telegram message. Returns True on success."""
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            log.info("Telegram message sent to %s (%d chars)", chat_id, len(text))
            return True
        log.warning("Telegram returned %d for chat %s: %s", resp.status_code, chat_id, resp.text[:200])
        return False
    except Exception as e:
        log.error("Telegram send failed for chat %s: %s", chat_id, e)
        return False


def send_batch(listings: list[dict]) -> int:
    """
    Format all listings and send to all configured chat IDs.
    Splits into chunks if the message exceeds Telegram's 4096 char limit.
    Returns number of successful sends.
    """
    if not listings or not TELEGRAM_CHAT_IDS:
        return 0

    divider = "\n---\n"
    header = f"🏠 *{len(listings)} new listing{'s' if len(listings) != 1 else ''}*\n---\n"
    blocks = [_format_listing(l) for l in listings]

    # Build chunks within MAX_CHARS
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
    for chat_id in TELEGRAM_CHAT_IDS:
        chat_id = chat_id.strip()
        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(1)
            if _send_raw(chat_id, chunk):
                sent += 1

    return sent
