"""Barcodes (GTIN-8, UPC-12, EAN-13, GTIN-14) from store pages."""

from __future__ import annotations

import re

_LENGTHS = (8, 12, 13, 14)


def _check_digit_ok(digits: str) -> bool:
    """GS1 check digit: weights 3 and 1 alternate from the right, skipping the check digit."""
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def normalize_gtin(value: str | int | None) -> str | None:
    """A valid barcode as 14 digits, or None.

    Padding to 14 digits makes the same product match whether a store writes
    its UPC-12 or its EAN-13 ("0" + UPC). Spaces and dashes are ignored; anything
    else, a wrong length, all zeros or a bad check digit gives None.
    """
    if value is None or isinstance(value, bool):
        return None
    text = re.sub(r"[\s-]", "", str(value))
    if not text.isdigit() or len(text) not in _LENGTHS or not text.strip("0"):
        return None
    if not _check_digit_ok(text):
        return None
    return text.zfill(14)
