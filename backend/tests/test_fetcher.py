import httpx
import pytest

from price_diaries.fetcher import Fetcher, FetchError, StoreBlockedError, _check_blocked

URL = "https://www.sephora.com.tr/p/demo-tonik-P1.html"


async def _get(status: int, robots: str = "User-agent: *\nAllow: /\n") -> str:
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots)
        return httpx.Response(status, text="")

    client = httpx.AsyncClient(transport=httpx.MockTransport(answer))
    async with Fetcher(min_delay=0, max_delay=0, client=client) as fetcher:
        return await fetcher.get(URL)


async def test_robots_txt_is_respected():
    with pytest.raises(FetchError, match="robots.txt asks bots not to fetch this page"):
        await _get(200, robots="User-agent: *\nDisallow: /p/\n")


async def test_forbidden_says_store_blocks_checks():
    with pytest.raises(StoreBlockedError, match="www.sephora.com.tr blocks automated price checks"):
        await _get(403)


async def test_rate_limited_says_try_later():
    with pytest.raises(StoreBlockedError, match=r"limiting automated requests \(429\)"):
        await _get(429)


async def test_other_errors_are_not_blocks():
    with pytest.raises(FetchError, match="Store answered 503.") as info:
        await _get(503)
    assert not isinstance(info.value, StoreBlockedError)


def test_access_denied_page_counts_as_blocked():
    # What a headless browser receives from an Akamai-protected store.
    html = "<html><head><title>Access Denied</title></head><body>Access Denied</body></html>"
    with pytest.raises(StoreBlockedError, match=r"blocks automated price checks\. ") as info:
        _check_blocked("www.sephora.com.tr", 200, html)
    assert "(200)" not in str(info.value)


def test_normal_page_is_not_blocked():
    _check_blocked("www.sephora.com.tr", 200, "<title>Glycolic Acid Toner</title>")
