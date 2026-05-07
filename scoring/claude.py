"""
Claude Haiku scorer — scores each enriched listing 1-10 against preferences.yaml.
Uses structured output (JSON mode) for reliable parsing.
~$0.01 per listing with Haiku.
"""
import json
import logging
import yaml
import anthropic
from config import ANTHROPIC_API_KEY

log = logging.getLogger(__name__)

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _load_preferences() -> str:
    with open("preferences.yaml") as f:
        return f.read()


SYSTEM_PROMPT = """\
You are a London apartment scoring assistant. You evaluate rental listings against a buyer's
stated preferences and return a structured JSON score.

Rules:
- Score 1-10 where 10 is perfect, 1 is completely unsuitable
- A listing that violates any deal_breaker must score ≤ 3
- Missing data (e.g. no EPC rating, no crime data) should not penalise the score heavily — note it in deal_flags
- A listing that is unusually strong on one dimension (e.g. 15 min commute, or £400 under budget)
  can compensate for minor weaknesses — bump the score up accordingly
- Return ONLY valid JSON with no surrounding text
"""

SCORE_TEMPLATE = """\
Score this London rental apartment against the preferences below.

PREFERENCES:
{preferences}

APARTMENT DATA:
{listing}

Return JSON in exactly this format:
{{
  "score": <integer 1-10>,
  "rationale": "<2-3 sentence explanation focusing on the most important factors>",
  "area_summary": "<one short sentence describing the neighbourhood vibe, e.g. 'Quiet residential street in Herne Hill, popular with young professionals'>",
  "deal_flags": ["<flag1>", "<flag2>"]
}}
deal_flags should list any deal-breaker violations, strong positives, or data gaps worth highlighting.
"""


def score(listing: dict) -> dict:
    """
    Returns dict with keys: score (int), rationale (str), deal_flags (list[str]).
    Falls back to score=0 on error so the pipeline can continue.
    """
    preferences = _load_preferences()

    listing_summary = {
        "address": listing.get("address"),
        "postcode": listing.get("postcode"),
        "price_pcm": listing.get("price_pcm"),
        "bedrooms": listing.get("bedrooms"),
        "furnished": listing.get("furnished"),
        "commute_mins_tfl": listing.get("commute_mins"),
        "cycling_mins": listing.get("cycling_mins"),
        "cycling_km": listing.get("cycling_km"),
        "is_basement": listing.get("is_basement", False),
        "floor_number": listing.get("floor_number"),  # -1=basement/lower-ground, 0=ground, 1=first, 99=top, None=unknown
        "description": (listing.get("description") or "")[:1500],
        "url": listing.get("url"),
    }

    prompt = SCORE_TEMPLATE.format(
        preferences=preferences,
        listing=json.dumps(listing_summary, indent=2),
    )

    try:
        client = _get_client()
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)
        return {
            "score": int(result.get("score", 0)),
            "rationale": str(result.get("rationale", "")),
            "area_summary": str(result.get("area_summary", "")),
            "deal_flags": list(result.get("deal_flags", [])),
        }
    except json.JSONDecodeError as e:
        log.warning("Score JSON parse failed for %s: %s", listing.get("listing_id"), e)
        return {"score": 0, "rationale": "Parse error", "deal_flags": ["scoring_error"]}
    except Exception as e:
        log.error("Scoring failed for %s: %s", listing.get("listing_id"), e)
        return {"score": 0, "rationale": str(e), "deal_flags": ["scoring_error"]}
