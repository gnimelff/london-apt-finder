import time
import random
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Raise this for permanent failures so tenacity doesn't waste time retrying
class PermanentHTTPError(Exception):
    pass

# Status codes that are permanent — cloud IP blocked, auth required, etc.
_NO_RETRY_STATUSES = {400, 401, 403, 404, 405, 410}


def polite_delay(min_s: float = 2.0, max_s: float = 5.0):
    time.sleep(random.uniform(min_s, max_s))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)),
    reraise=True,
)
def fetch(url: str, params: dict | None = None, extra_headers: dict | None = None) -> httpx.Response:
    headers = {**HEADERS, **(extra_headers or {})}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=20) as client:
        resp = client.get(url, params=params)
        if resp.status_code in _NO_RETRY_STATUSES:
            raise PermanentHTTPError(f"HTTP {resp.status_code} for {url} (not retrying)")
        resp.raise_for_status()
        return resp
