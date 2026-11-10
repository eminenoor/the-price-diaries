"""Supported stores and how to find the price on each one.

Every store first tries the generic strategies in ``Parser`` (JSON-LD and
meta tags), then the store's own CSS selectors.

Store HTML changes over time. When a store stops working: open a product
page, inspect the price in your browser's dev tools, update the selectors
here, and add a saved HTML sample to ``tests/fixtures`` so it stays fixed.
"""

from __future__ import annotations

from dataclasses import dataclass

from price_diaries.parsers.base import Parser

_COMMON = ("[itemprop='price']", "[class*='sale-price' i]", "[class*='product-price' i]")


@dataclass(frozen=True)
class Store:
    key: str
    name: str
    domains: tuple[str, ...]
    selectors: tuple[str, ...] = ()
    needs_browser: bool = False  # prices rendered by JavaScript

    def parser(self) -> Parser:
        return Parser((*self.selectors, *_COMMON))


STORES: tuple[Store, ...] = (
    Store(
        "gratis",
        "Gratis",
        ("gratis.com", "www.gratis.com"),
        ("[class*='discounted-price' i]", "[class*='price' i]"),
    ),
    Store(
        "trendyol",
        "Trendyol",
        ("trendyol.com", "www.trendyol.com"),
        (".prc-dsc", ".product-price-container .prc-org", "[class*='price' i]"),
        needs_browser=True,
    ),
    Store(
        "amazon",
        "Amazon",
        ("amazon.com.tr", "www.amazon.com.tr", "amazon.com", "www.amazon.com"),
        (
            "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
            "#corePrice_feature_div .a-price .a-offscreen",
            ".a-price .a-offscreen",
        ),
    ),
    Store(
        "watsons",
        "Watsons",
        ("watsons.com.tr", "www.watsons.com.tr"),
        ("[class*='price' i]",),
    ),
    Store(
        "rossmann",
        "Rossmann",
        ("rossmann.com.tr", "www.rossmann.com.tr"),
        ("[class*='price' i]",),
    ),
    Store(
        "eveshop",
        "Eve Shop",
        ("eveshop.com.tr", "www.eveshop.com.tr"),
        ("[class*='price' i]",),
    ),
    Store(
        "sephora",
        "Sephora",
        ("sephora.com.tr", "www.sephora.com.tr"),
        ("[class*='price' i]",),
        needs_browser=True,
    ),
)

_BY_DOMAIN = {domain: store for store in STORES for domain in store.domains}


def store_for_host(host: str) -> Store | None:
    return _BY_DOMAIN.get(host.lower())
