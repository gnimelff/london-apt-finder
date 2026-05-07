"""
Main pipeline — scrape → dedup → enrich → score → notify.
Designed to be run as a one-shot script by GitHub Actions cron.
"""
import logging
import sys
from db import init_db, is_empty, seed, filter_new, save_listing, mark_notified
from scrapers import openrent, rightmove, onthemarket
from enrichment.pipeline import enrich
from scoring.claude import score
from notifications.telegram import send_batch, send_alert
from config import SCORE_THRESHOLD

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


def run():
    log.info("=== London Apt Finder starting ===")
    init_db()

    # 1. Scrape all sites
    raw_listings: list[dict] = []
    for scraper_name, scraper_fn in [
        ("OpenRent", openrent.scrape),
        ("Rightmove", rightmove.scrape),
        ("OnTheMarket", onthemarket.scrape),
    ]:
        try:
            found = scraper_fn()
            log.info("%s: %d listings", scraper_name, len(found))
            raw_listings.extend(found)
        except Exception as e:
            log.error("%s scraper failed: %s", scraper_name, e)
            send_alert(f"⚠️ {scraper_name} scraper failed")

    log.info("Total scraped: %d", len(raw_listings))

    # 2. First-run seed: if DB is empty, just mark everything as seen and exit.
    #    This prevents a flood of 100+ notifications on the very first run.
    if is_empty():
        seed(raw_listings)
        log.info("First run — seeded %d listings into seen.db. Will process new ones next run.", len(raw_listings))
        return

    # 3. Deduplicate
    new_listings = filter_new(raw_listings)
    log.info("New (unseen): %d", len(new_listings))

    if not new_listings:
        log.info("Nothing new. Done.")
        return

    # 4. Filter obvious mismatches before enrichment (saves API calls)
    candidates = [
        l for l in new_listings
        if _pre_filter(l)
    ]
    log.info("Pre-filter passed: %d / %d", len(candidates), len(new_listings))

    to_notify = []
    for listing in candidates:
        log.info("Processing: %s [%s] £%s", listing.get("address"), listing.get("site"), listing.get("price_pcm"))

        # 4. Enrich
        listing = enrich(listing)

        # Skip scoring if commute is too long (saves Claude credits)
        commute = listing.get("commute_mins")
        if commute is not None and commute > 45:
            log.info("  Skipping (commute %d min > 45)", commute)
            save_listing(listing)
            continue

        # 5. Score
        result = score(listing)
        listing.update(result)
        log.info("  Score: %d/10 — %s", listing["score"], listing.get("rationale", "")[:80])

        # 6. Save to DB
        row_id = save_listing(listing)
        listing["_row_id"] = row_id

        if listing["score"] >= SCORE_THRESHOLD:
            to_notify.append(listing)

    # 7. Send all high-scoring listings in one batched WhatsApp message
    to_notify.sort(key=lambda l: l.get("score", 0), reverse=True)
    if to_notify:
        chunks_sent = send_batch(to_notify)
        if chunks_sent:
            for listing in to_notify:
                mark_notified(listing["_row_id"])
        log.info("=== Done. Notified: %d listings in %d message(s) ===", len(to_notify), chunks_sent)
    else:
        log.info("=== Done. No listings above threshold ===")


_SHARED_KEYWORDS = {
    "room in", "room only", "house share", "houseshare", "house-share",
    "flat share", "flatshare", "flat-share", "shared house", "shared flat",
    "shared accommodation", "en suite", "ensuite",
}


def _pre_filter(listing: dict) -> bool:
    """Quick check to skip obvious mismatches before spending enrichment API calls."""
    # Skip incomplete listings
    if not listing.get("address"):
        return False
    if not listing.get("price_pcm"):
        return False

    price = listing.get("price_pcm")
    beds = listing.get("bedrooms", 0)

    if price and price > 3200:
        return False
    if beds is not None and beds < 1:
        return False

    # Exclude rooms in shared flats — check address + description
    combined = " ".join([
        str(listing.get("address", "")),
        str(listing.get("description", "")),
    ]).lower()
    if any(kw in combined for kw in _SHARED_KEYWORDS):
        log.info("Skipping shared/room listing: %s", listing.get("address"))
        return False

    return True


if __name__ == "__main__":
    run()
