"""Parser interface and the generic strategies every site parser can reuse."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

from price_diaries.parsers.price_text import detect_currency, parse_price


@dataclass(frozen=True)
class ParsedPrice:
    price: float
    currency: str = "TRY"
    in_stock: bool = True
    source: str = "unknown"  # which strategy found it; handy when debugging


class PriceNotFoundError(LookupError):
    """Raised when no strategy could find a price on the page."""


class Parser:
    """Finds a price in HTML: custom selector, then JSON-LD, meta tags, store selectors."""

    def __init__(self, extra_selectors: tuple[str, ...] = ()) -> None:
        self.extra_selectors = extra_selectors

    def parse(self, html: str, selector: str | None = None) -> ParsedPrice:
        soup = BeautifulSoup(html, "html.parser")

        strategies = []
        if selector:
            strategies.append(lambda: _from_selectors(soup, (selector,), "custom-selector"))
        strategies += [
            lambda: _from_json_ld(soup),
            lambda: _from_meta(soup),
            lambda: _from_selectors(soup, self.extra_selectors, "site-selector"),
        ]

        for strategy in strategies:
            result = strategy()
            if result is not None:
                return result
        raise PriceNotFoundError("No price found on page. Try adding a 'selector' for it.")


# --- strategies -----------------------------------------------------------


def _from_json_ld(soup: BeautifulSoup) -> ParsedPrice | None:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _walk(data):
            if not _is_type(node, "Product"):
                continue
            found = _price_from_offers(node.get("offers"))
            if found:
                return found
    return None


def _price_from_offers(offers: Any) -> ParsedPrice | None:
    for offer in _as_list(offers):
        if not isinstance(offer, dict):
            continue
        raw = offer.get("price", offer.get("lowPrice"))
        if raw is None and isinstance(offer.get("priceSpecification"), dict):
            raw = offer["priceSpecification"].get("price")
        price = parse_price(raw)
        if price is None:
            continue
        availability = str(offer.get("availability", "")).lower()
        return ParsedPrice(
            price=price,
            currency=offer.get("priceCurrency") or "TRY",
            in_stock="outofstock" not in availability,
            source="json-ld",
        )
    return None


def _from_meta(soup: BeautifulSoup) -> ParsedPrice | None:
    candidates = [
        ({"itemprop": "price"}, {"itemprop": "priceCurrency"}),
        ({"property": "product:price:amount"}, {"property": "product:price:currency"}),
        ({"property": "og:price:amount"}, {"property": "og:price:currency"}),
    ]
    for price_attrs, currency_attrs in candidates:
        tag = soup.find(attrs=price_attrs)
        if tag is None:
            continue
        price = parse_price(tag.get("content") or tag.get_text(" ", strip=True))
        if price is None:
            continue
        cur_tag = soup.find(attrs=currency_attrs)
        currency = (cur_tag.get("content") if cur_tag else None) or "TRY"
        return ParsedPrice(price=price, currency=currency, source="meta")
    return None


def _from_selectors(
    soup: BeautifulSoup, selectors: tuple[str, ...], source: str
) -> ParsedPrice | None:
    for css in selectors:
        tag = soup.select_one(css)
        if tag is None:
            continue
        text = tag.get("content") or tag.get_text(" ", strip=True)
        price = parse_price(text)
        if price is not None:
            return ParsedPrice(price=price, currency=detect_currency(text), source=source)
    return None


# --- helpers --------------------------------------------------------------


def _walk(data: Any):
    """Yield every dict inside nested JSON-LD (handles @graph and lists)."""
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from _walk(value)
    elif isinstance(data, list):
        for item in data:
            yield from _walk(item)


def _is_type(node: dict, name: str) -> bool:
    node_type = node.get("@type")
    return name in node_type if isinstance(node_type, list) else node_type == name


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
