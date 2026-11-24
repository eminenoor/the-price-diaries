"""Fetch the current price of products and store it."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from price_diaries.db import CheckFailure, PricePoint, Product
from price_diaries.fetcher import FetchError, StoreBlockedError
from price_diaries.parsers import ParsedPrice, PriceNotFoundError, Size, parse_size, store_for_host

log = logging.getLogger(__name__)


class PageSource(Protocol):
    async def get(self, url: str) -> str: ...
    async def get_rendered(self, url: str) -> str: ...


@dataclass(frozen=True)
class CheckOutcome:
    product_id: int
    ok: bool
    price: float | None = None
    error: str | None = None


async def fetch_price(product: Product, source: PageSource, browser_fallback: bool) -> ParsedPrice:
    store = store_for_host(urlsplit(product.url).hostname or "")
    if store is None:
        raise PriceNotFoundError("Store is no longer supported.")
    parser = store.parser()

    if not store.needs_browser:
        try:
            parsed = parser.parse(await source.get(product.url))
        except PriceNotFoundError:
            if not browser_fallback:
                raise
            log.info("%s: no price in raw HTML, trying the browser", product.name)
        else:
            if parsed.member_price is not None or not store.member_labels or not browser_fallback:
                return parsed
            # Member prices are often added by JavaScript after the page loads.
            try:
                rendered = parser.parse(await source.get_rendered(product.url))
            except (FetchError, PriceNotFoundError) as exc:
                log.info("%s: kept regular price, member price unavailable: %s", product.name, exc)
                return parsed
            return rendered if rendered.member_price is not None else parsed

    html = await source.get_rendered(product.url)
    return parser.parse(html)


def update_size(product: Product, page_size: Size | None = None) -> None:
    """Fill in the pack size: from the product's name first, then from the store page.

    A size the user set (or removed) is never changed. A size from the page is
    kept when a later page doesn't show one.
    """
    if product.size_source == "user":
        return
    size, source = parse_size(product.name), "name"
    if size is None:
        size, source = page_size, "page"
    if size is None:
        if product.size_source == "page":
            return
        product.size_amount = product.size_unit = product.size_source = None
        return
    product.size_amount, product.size_unit, product.size_source = size.amount, size.unit, source


def update_group(product: Product, gtin: str | None) -> None:
    """Remember the barcode, and group the product with others that share it.

    A product the user linked or unlinked by hand keeps its group.
    """
    if gtin:
        product.gtin = gtin
    if product.group_source != "user" and product.gtin:
        product.group_key, product.group_source = f"gtin:{product.gtin}", "barcode"


def _is_blocked(exc: Exception) -> bool:
    """The store refuses automated checks. A 429 (slow down) is temporary, so it isn't."""
    return isinstance(exc, StoreBlockedError) and exc.status != 429


def _failed(session: Session, product: Product, exc: Exception, at: datetime) -> None:
    """Show the error on the product, and keep it for the Sunday paper."""
    product.last_error = str(exc)[:500]
    product.blocked = _is_blocked(exc)
    session.add(CheckFailure(product_id=product.id, error=product.last_error, checked_at=at))


async def check_product(
    session: Session, product: Product, source: PageSource, browser_fallback: bool = True
) -> CheckOutcome:
    try:
        parsed = await fetch_price(product, source, browser_fallback)
    except (FetchError, PriceNotFoundError) as exc:
        _failed(session, product, exc, datetime.now())
        session.commit()
        log.warning("%s: %s", product.name, exc)
        return CheckOutcome(product.id, ok=False, error=product.last_error)

    session.add(
        PricePoint(
            product_id=product.id,
            price=parsed.price,
            member_price=parsed.member_price,
            currency=parsed.currency,
            in_stock=parsed.in_stock,
            checked_at=datetime.now(),
        )
    )
    product.last_error = None
    product.blocked = False
    product.image_url = parsed.image_url or product.image_url
    if product.brand is None:  # never overwrite a brand the user set or removed
        product.brand = parsed.brand
    update_size(product, parsed.size)
    update_group(product, parsed.gtin)
    session.commit()
    log.info("%s: %.2f %s (%s)", product.name, parsed.price, parsed.currency, parsed.source)
    return CheckOutcome(product.id, ok=True, price=parsed.member_price or parsed.price)


async def check_all(
    session: Session, source: PageSource, browser_fallback: bool = True
) -> list[CheckOutcome]:
    """Check every product. Stores run in parallel; one store is checked one page at a time
    (the fetcher enforces that), so we never hammer a single site."""
    products = session.scalars(select(Product)).all()
    # Fetching is concurrent, but SQLite writes go through one session, so we
    # gather the network part and write results sequentially.
    prices = await asyncio.gather(
        *(fetch_price(p, source, browser_fallback) for p in products), return_exceptions=True
    )

    outcomes = []
    now = datetime.now()
    for product, result in zip(products, prices, strict=True):
        if isinstance(result, (FetchError, PriceNotFoundError)):
            _failed(session, product, result, now)
            outcomes.append(CheckOutcome(product.id, ok=False, error=product.last_error))
        elif isinstance(result, BaseException):
            raise result
        else:
            session.add(
                PricePoint(
                    product_id=product.id,
                    price=result.price,
                    member_price=result.member_price,
                    currency=result.currency,
                    in_stock=result.in_stock,
                    checked_at=now,
                )
            )
            product.last_error = None
            product.blocked = False
            product.image_url = result.image_url or product.image_url
            if product.brand is None:
                product.brand = result.brand
            update_size(product, result.size)
            update_group(product, result.gtin)
            outcomes.append(
                CheckOutcome(product.id, ok=True, price=result.member_price or result.price)
            )
    session.commit()
    return outcomes
