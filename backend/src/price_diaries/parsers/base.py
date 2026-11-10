"""Parser interface and the generic strategies every site parser can reuse."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from typing import Any

from bs4 import BeautifulSoup

from price_diaries.parsers.price_text import detect_currency, parse_price


@dataclass(frozen=True)
class ParsedPrice:
    price: float
    currency: str = "TRY"
    in_stock: bool = True
    source: str = "unknown"  # which strategy found it; handy when debugging
    member_price: float | None = None  # loyalty-card price, e.g. Gratis Gold & Platinum
    image_url: str | None = None  # product photo (og:image or JSON-LD), https only


class PriceNotFoundError(LookupError):
    """Raised when no strategy could find a price on the page."""


class Parser:
    """Finds a price in HTML: custom selector, then JSON-LD, meta tags, store selectors.

    ``member_labels`` are regular expressions for the text a store prints next to
    its loyalty-card price (Gratis: "Gold&Platinum Özel Fiyat"). Matching on that
    visible text instead of CSS classes keeps working when the store redesigns.
    """

    def __init__(
        self, extra_selectors: tuple[str, ...] = (), member_labels: tuple[str, ...] = ()
    ) -> None:
        self.extra_selectors = extra_selectors
        self.member_labels = member_labels

    def parse(self, html: str, selector: str | None = None) -> ParsedPrice:
        soup = BeautifulSoup(html, "html.parser")
        for _, strategy in self._strategies(soup, selector):
            result = strategy()
            if result is not None:
                member = _member_price(soup, self.member_labels)
                if member is not None and member < result.price:
                    result = replace(result, member_price=member)
                return replace(result, image_url=_image_url(soup))
        raise PriceNotFoundError("No price found on page. Try adding a 'selector' for it.")

    def explain(self, html: str, selector: str | None = None) -> dict[str, float | None]:
        """What every strategy finds on the page. Used by `price-diaries inspect`."""
        soup = BeautifulSoup(html, "html.parser")
        found = {}
        for name, strategy in self._strategies(soup, selector):
            result = strategy()
            found[name] = result.price if result else None
        found["member price"] = _member_price(soup, self.member_labels)
        return found

    def _strategies(self, soup: BeautifulSoup, selector: str | None):
        if selector:
            yield "custom selector", lambda: _from_selectors(soup, (selector,), "custom-selector")
        yield "json-ld", lambda: _from_json_ld(soup)
        yield "meta tags", lambda: _from_meta(soup)
        yield (
            "store selectors",
            lambda: _from_selectors(soup, self.extra_selectors, "site-selector"),
        )


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


def _member_price(soup: BeautifulSoup, labels: tuple[str, ...]) -> float | None:
    """Find the price printed right after a loyalty-card label.

    The label and the price are usually separate elements inside one box, so
    we climb from the label towards its ancestors until the box's text has a
    price after the label.
    """
    for label in labels:
        pattern = re.compile(label, re.IGNORECASE)
        for text_node in soup.find_all(string=pattern):
            element = text_node.parent
            for _ in range(4):
                if element is None:
                    break
                text = element.get_text(" ", strip=True)
                match = pattern.search(text)
                if match:
                    after = text[match.end() :]
                    if re.search(r"\d", after):
                        return parse_price(after)
                element = element.parent
    return None


def _image_url(soup: BeautifulSoup) -> str | None:
    """The product photo: og:image first, then the JSON-LD Product image.

    Only absolute https URLs are kept. The browser loads them, never the server.
    """
    candidates: list[Any] = []
    for attrs in ({"property": "og:image"}, {"name": "og:image"}):
        tag = soup.find("meta", attrs=attrs)
        if tag is not None:
            candidates.append(tag.get("content"))
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _walk(data):
            if _is_type(node, "Product"):
                for image in _as_list(node.get("image")):
                    candidates.append(image.get("url") if isinstance(image, dict) else image)
    for url in candidates:
        if isinstance(url, str) and url.startswith("https://") and len(url) <= 2048:
            return url.strip()
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
