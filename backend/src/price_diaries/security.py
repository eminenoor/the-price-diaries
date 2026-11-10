"""Validate product URLs before the server ever fetches them.

The app downloads whatever URL a user saves, which is a classic
server-side request forgery (SSRF) risk: a crafted URL could make the
server call internal services (http://localhost:8000/..., cloud metadata
endpoints, private IPs). We prevent that with an allowlist: only HTTPS
URLs on known store domains, with no credentials or custom ports.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from price_diaries.parsers import Store, store_for_host

# Query parameters that only track marketing campaigns; dropping them means
# the same product pasted twice is stored once.
# (Trendyol's merchantId is kept on purpose: it selects the seller, which changes the price.)
_TRACKING_PREFIXES = ("utm_", "gclid", "fbclid", "ref=", "ref_=")


class UnsupportedURLError(ValueError):
    pass


def validate_product_url(raw: str) -> tuple[str, Store]:
    """Return a normalized URL and its store, or raise UnsupportedURLError."""
    url = raw.strip()
    parts = urlsplit(url)

    if parts.scheme != "https":
        raise UnsupportedURLError("Only https:// links are supported.")
    if parts.username or parts.password:
        raise UnsupportedURLError("Links with embedded credentials are not allowed.")
    if parts.port not in (None, 443):
        raise UnsupportedURLError("Links with custom ports are not allowed.")

    store = store_for_host(parts.hostname or "")
    if store is None:
        raise UnsupportedURLError(
            f"'{parts.hostname}' is not a supported store. Add it in parsers/sites.py first."
        )

    query = "&".join(
        pair
        for pair in parts.query.split("&")
        if pair and not pair.lower().startswith(_TRACKING_PREFIXES)
    )
    normalized = urlunsplit(("https", parts.hostname.lower(), parts.path, query, ""))
    return normalized, store
