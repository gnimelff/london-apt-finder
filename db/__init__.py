import hashlib
import json
import sqlite3
from pathlib import Path

DB_PATH = Path("seen.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS seen_listings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                site        TEXT NOT NULL,
                listing_id  TEXT NOT NULL,
                dedup_hash  TEXT,
                first_seen  TEXT DEFAULT (datetime('now')),
                UNIQUE(site, listing_id)
            );
            CREATE INDEX IF NOT EXISTS idx_seen_dedup_hash ON seen_listings(dedup_hash);

            CREATE TABLE IF NOT EXISTS listings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                seen_listing_id INTEGER REFERENCES seen_listings(id),
                url             TEXT,
                address         TEXT,
                postcode        TEXT,
                price_pcm       INTEGER,
                bedrooms        INTEGER,
                furnished       INTEGER,
                lat             REAL,
                lng             REAL,
                commute_mins    INTEGER,
                crime_count     INTEGER,
                epc_rating      TEXT,
                score           INTEGER,
                rationale       TEXT,
                deal_flags      TEXT,
                notified_at     TEXT,
                raw_data        TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_listings_score ON listings(score DESC);
            CREATE INDEX IF NOT EXISTS idx_listings_created ON listings(created_at DESC);
        """)


def _dedup_hash(listing: dict) -> str:
    key = f"{listing.get('postcode', '')}|{listing.get('price_pcm', '')}|{listing.get('bedrooms', '')}"
    return hashlib.md5(key.encode()).hexdigest()


def filter_new(listings: list[dict]) -> list[dict]:
    """Return only listings not already in seen_listings (by site+id or dedup_hash)."""
    if not listings:
        return []

    new = []
    with get_conn() as conn:
        for l in listings:
            site = l["site"]
            listing_id = str(l["listing_id"])
            h = _dedup_hash(l)

            row = conn.execute(
                "SELECT 1 FROM seen_listings WHERE (site=? AND listing_id=?) OR dedup_hash=? LIMIT 1",
                (site, listing_id, h),
            ).fetchone()

            if row:
                continue

            conn.execute(
                "INSERT OR IGNORE INTO seen_listings (site, listing_id, dedup_hash) VALUES (?,?,?)",
                (site, listing_id, h),
            )
            l["_seen_id"] = None
            new.append(l)

    return new


def save_listing(listing: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO listings
              (seen_listing_id, url, address, postcode, price_pcm, bedrooms, furnished,
               lat, lng, commute_mins, crime_count, epc_rating,
               score, rationale, deal_flags, raw_data)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                listing.get("_seen_id"),
                listing.get("url"),
                listing.get("address"),
                listing.get("postcode"),
                listing.get("price_pcm"),
                listing.get("bedrooms"),
                int(listing["furnished"]) if listing.get("furnished") is not None else None,
                listing.get("lat"),
                listing.get("lng"),
                listing.get("commute_mins"),
                listing.get("crime_count"),
                listing.get("epc_rating"),
                listing.get("score"),
                listing.get("rationale"),
                json.dumps(listing.get("deal_flags", [])),
                json.dumps(listing),
            ),
        )
        return cur.lastrowid


def mark_notified(listing_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE listings SET notified_at=datetime('now') WHERE id=?",
            (listing_id,),
        )
