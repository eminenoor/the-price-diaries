"""HTML -> price extraction, one configuration per store."""

from price_diaries.parsers.base import ParsedPrice, Parser, PriceNotFoundError
from price_diaries.parsers.gtin_text import normalize_gtin
from price_diaries.parsers.price_text import detect_currency, parse_price
from price_diaries.parsers.sites import STORES, Store, store_for_host, store_name
from price_diaries.parsers.size_text import Size, SizeUnit, parse_size, with_size

__all__ = [
    "STORES",
    "ParsedPrice",
    "Parser",
    "PriceNotFoundError",
    "Size",
    "SizeUnit",
    "Store",
    "detect_currency",
    "normalize_gtin",
    "parse_price",
    "parse_size",
    "store_for_host",
    "store_name",
    "with_size",
]
