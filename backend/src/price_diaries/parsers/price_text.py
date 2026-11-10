"""Turn human-written price strings into floats.

Handles both Turkish/European formatting ("1.299,90 TL") and
English formatting ("1,299.90"), plus currency symbols and words.
"""

from __future__ import annotations

import re

_CURRENCY_HINTS = {
    "₺": "TRY",
    "TL": "TRY",
    "TRY": "TRY",
    "€": "EUR",
    "EUR": "EUR",
    "$": "USD",
    "USD": "USD",
    "£": "GBP",
    "GBP": "GBP",
}

_NUMBER_RE = re.compile(r"\d[\d.,\s]*")


def parse_price(text: str | float | int | None) -> float | None:
    """Return the first price found in ``text`` as a float, or None."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)

    match = _NUMBER_RE.search(str(text))
    if not match:
        return None
    raw = match.group(0).replace(" ", "").replace(" ", "").rstrip(".,")

    last_dot, last_comma = raw.rfind("."), raw.rfind(",")
    if last_dot != -1 and last_comma != -1:
        # The separator that appears last is the decimal separator.
        if last_comma > last_dot:
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif last_comma != -1:
        # "289,99" -> decimal comma; "1,299" -> thousands comma.
        decimals = len(raw) - last_comma - 1
        raw = raw.replace(",", ".") if decimals in (1, 2) else raw.replace(",", "")
    elif last_dot != -1:
        # "1.299" (Turkish thousands) vs "289.99" (decimal point).
        decimals = len(raw) - last_dot - 1
        if decimals == 3 and raw.count(".") >= 1:
            raw = raw.replace(".", "")

    try:
        return float(raw)
    except ValueError:
        return None


def detect_currency(text: str | None, default: str = "TRY") -> str:
    if not text:
        return default
    upper = str(text).upper()
    for hint, code in _CURRENCY_HINTS.items():
        if hint in upper or hint in str(text):
            return code
    return default
