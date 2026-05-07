"""
Telegram Bot notifications — free, reliable, no rate limits for personal use.

Setup (one-time):
  1. Message @BotFather on Telegram → /newbot → get your token
  2. Start a chat with your bot, then fetch:
     https://api.telegram.org/bot<TOKEN>/getUpdates
     to get your chat_id
  3. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS in .env / GitHub secrets
     TELEGRAM_CHAT_IDS is a comma-separated list for multiple recipients

Note: Uses HTML parse mode (not Markdown) because Rightmove URLs contain
underscores (channel=RES_LET) which break Telegram's Markdown italic parsing.
"""
import html
import re
import time
import logging
import httpx
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS

log = logging.getLogger(__name__)

MAX_CHARS = 4000  # Telegram's limit is 4096


def _b(text: str) -> str:
    """Wrap text in HTML bold tags, escaping any HTML special chars."""
    return f"<b>{html.escape(str(text))}</b>"


def _e(text: str) -> str:
    """Escape HTML special chars in plain text."""
    return html.escape(str(text))


# Skip flags about fields already shown in the stats line, or pure data-gap noise
_SKIP_IF_CONTAINS = {
    # Already visible in stats: price, commute, EPC, crime, cycling
    "commute", "budget", "price", "pcm", "epc", "crime", "cycling", "bicycle",
    # Data gaps — nothing actionable
    "missing", "not provided", "unable to verify", "unable to assess",
    "not available", "not confirmed", "cannot verify", "cannot confirm",
    "cannot fully confirm", "no data", "not found",
}


def _should_skip(flag: str) -> bool:
    fl = flag.lower()
    return any(kw in fl for kw in _SKIP_IF_CONTAINS)


def _flag_icon(flag: str) -> str:
    """✅ for ✓, ⚠️ for ✗, ❓ for ? or unclear wording."""
    if "✓" in flag:
        return "✅"
    if "✗" in flag:
        return "⚠️"
    if "?" in flag:
        return "❓"
    _UNCLEAR = {"unclear", "not stated", "not specified", "unknown"}
    if any(w in flag.lower() for w in _UNCLEAR):
        return "❓"
    return "⚠️"


def _format_listing(listing: dict) -> str:
    score = listing.get("score", "?")
    address = listing.get("address", "Unknown address")
    # Strip ", London" when it's a standalone city component (not part of "London Road" etc.)
    # Strip ", London" when it's a standalone city label (not "London Road" etc.)
    # Handles: ", London, SE1" / ", London SE1" / ", London" at end
    address = re.sub(r",\s*London(?=,|$|\s+[A-Z]{1,2}\d)", "", address).strip(", ")
    price = listing.get("price_pcm")
    price_str = f"£{price:,}/mo" if price else "price unknown"
    commute = listing.get("commute_mins")
    commute_str = f"🚇 {commute}" if commute else "🚇 ?"
    cycling_mins = listing.get("cycling_mins")
    cycling_km = listing.get("cycling_km")
    cycling_str = f"🚴 {cycling_mins} ({cycling_km} km)" if cycling_mins and cycling_km else None
    url = listing.get("url", "")

    borough = listing.get("borough", "")
    borough_str = f" — {_e(borough)}" if borough else ""

    stats = f"{_b(price_str)} | {_e(commute_str)}"
    if cycling_str:
        stats += f" | {_e(cycling_str)}"

    lines = [
        f"{_b(f'Score {score}/10')} — {_e(str(listing.get('bedrooms', '?')))}-bed{borough_str}",
        _b(address),
        stats,
    ]

    # Deal flags — one per line, skip stats duplicates and data-gap noise
    for flag in (listing.get("deal_flags") or []):
        if not _should_skip(flag):
            # Strip leading ✓/✗/? markers Claude embeds — we replace them with our emoji
            clean = flag.lstrip("✓✗? ").strip()
            lines.append(f"{_flag_icon(flag)} {_e(clean)}")

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
                "parse_mode": "HTML",
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
    header = f"🏠 <b>{len(listings)} new listing{'s' if len(listings) != 1 else ''}</b>\n---\n"
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


def send_alert(text: str) -> None:
    """Send a plain-text alert (e.g. scraper failure) to all configured chat IDs."""
    if not TELEGRAM_CHAT_IDS:
        return
    for chat_id in TELEGRAM_CHAT_IDS:
        _send_raw(chat_id.strip(), html.escape(text))
