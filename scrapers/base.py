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


def polite_delay(min_s: float = 2.0, max_s: float = 5.0):
    time.sleep(random.uniform(min_s, max_s))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)),
)
def fetch(url: str, params: dict | None = None, extra_headers: dict | None = None) -> httpx.Response:
    headers = {**HEADERS, **(extra_headers or {})}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=20) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp
