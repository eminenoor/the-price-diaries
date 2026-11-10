"""HTML -> price extraction, one configuration per store."""

from price_diaries.parsers.base import ParsedPrice, Parser, PriceNotFoundError
from price_diaries.parsers.price_text import detect_currency, parse_price
from price_diaries.parsers.sites import STORES, Store, store_for_host

__all__ = [
    "STORES",
    "ParsedPrice",
    "Parser",
    "PriceNotFoundError",
    "Store",
    "detect_currency",
    "parse_price",
    "store_for_host",
]
