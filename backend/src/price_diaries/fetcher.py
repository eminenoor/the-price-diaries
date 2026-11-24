"""Download product pages politely.

- Requests to the same store are spaced out with a random delay; different
  stores are fetched concurrently.
- robots.txt is respected.
- Pages whose price is rendered by JavaScript can be loaded in a headless
  browser (Playwright), if it is installed.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import urllib.robotparser
from collections import defaultdict
from urllib.parse import urlsplit

import httpx

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36 price-diaries/0.1"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"}


class FetchError(RuntimeError):
    pass


class StoreBlockedError(FetchError):
    """The store refused automated access (403 or an "Access Denied" page) or rate-limited us.

    We never try to get around this; the message tells the user what happened instead.
    """

    def __init__(self, host: str, status: int | None) -> None:
        if status == 429:
            message = f"{host} is limiting automated requests (429). Try again later."
        else:
            code = f" ({status})" if status else ""
            message = (
                f"{host} blocks automated price checks{code}. "
                "This product can't be tracked automatically; check the price on the store's site."
            )
        super().__init__(message)
        self.host, self.status = host, status


def _check_blocked(host: str, status: int | None, html: str = "") -> None:
    if status in (403, 429):
        raise StoreBlockedError(host, status)
    if "<title>Access Denied</title>" in html:  # block page served with a 200
        raise StoreBlockedError(host, None)


class Fetcher:
    def __init__(
        self,
        min_delay: float = 3.0,
        max_delay: float = 7.0,
        timeout: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.min_delay, self.max_delay = min_delay, max_delay
        self.timeout = timeout
        self._client = client or httpx.AsyncClient(
            headers=HEADERS, timeout=timeout, follow_redirects=True
        )
        self._host_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    async def __aenter__(self) -> Fetcher:
        return self

    async def __aexit__(self, *_) -> None:
        await self._client.aclose()

    async def get(self, url: str) -> str:
        host = urlsplit(url).hostname or ""
        if not await self._allowed(url):
            raise FetchError("robots.txt asks bots not to fetch this page.")

        async with self._host_locks[host]:
            await self._wait_turn(host)
            try:
                response = await self._client.get(url)
                _check_blocked(host, response.status_code)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise FetchError(f"Store answered {exc.response.status_code}.") from exc
            except httpx.HTTPError as exc:
                raise FetchError(f"Network error: {exc.__class__.__name__}.") from exc
            return response.text

    async def get_rendered(self, url: str) -> str:
        """Load the page in headless Chromium and return the final HTML."""
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise FetchError(
                "This store needs a browser. Install it with: "
                "uv sync && uv run playwright install chromium"
            ) from exc

        host = urlsplit(url).hostname or ""
        async with self._host_locks[host]:
            await self._wait_turn(host)
            async with async_playwright() as pw:
                browser = await pw.chromium.launch()
                try:
                    page = await browser.new_page(user_agent=USER_AGENT, locale="tr-TR")
                    response = await page.goto(
                        url, wait_until="networkidle", timeout=self.timeout * 1000
                    )
                    html = await page.content()
                except Exception as exc:  # Playwright raises its own error types
                    raise FetchError(f"Browser could not load the page: {exc}") from exc
                finally:
                    await browser.close()
        _check_blocked(host, response.status if response else None, html)
        return html

    async def _wait_turn(self, host: str) -> None:
        delay = random.uniform(self.min_delay, self.max_delay)  # noqa: S311
        elapsed = time.monotonic() - self._last_hit.get(host, 0.0)
        if host in self._last_hit and elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_hit[host] = time.monotonic()

    async def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser = urllib.robotparser.RobotFileParser()
            try:
                resp = await self._client.get(f"{origin}/robots.txt")
                parser.parse(resp.text.splitlines() if resp.is_success else [])
                self._robots[origin] = parser
            except httpx.HTTPError:
                self._robots[origin] = None
        robots = self._robots[origin]
        return True if robots is None else robots.can_fetch(USER_AGENT, url)
