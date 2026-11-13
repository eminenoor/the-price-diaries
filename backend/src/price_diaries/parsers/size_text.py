"""Find a pack size ("150 ml", "1,5 L", "500 g", "60 adet") in product text.

Sizes are normalised to millilitres, grams or pieces, so products in different
pack sizes can be compared by unit price.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from price_diaries.parsers.price_text import parse_price

SizeUnit = Literal["ml", "g", "pcs"]

# Written unit -> (normalised unit, factor). Milligrams are left out on purpose:
# on supplements "1000 mg" is the dose per tablet, not the size of the pack.
_UNITS: dict[str, tuple[SizeUnit, float]] = {
    "ml": ("ml", 1),
    "cl": ("ml", 10),
    "l": ("ml", 1000),
    "lt": ("ml", 1000),
    "litre": ("ml", 1000),
    "liter": ("ml", 1000),
    "g": ("g", 1),
    "gr": ("g", 1),
    "gram": ("g", 1),
    "kg": ("g", 1000),
    "adet": ("pcs", 1),
    "pcs": ("pcs", 1),
    "pc": ("pcs", 1),
    "piece": ("pcs", 1),
    "pieces": ("pcs", 1),
    "tablet": ("pcs", 1),
    "tablets": ("pcs", 1),
    "kapsül": ("pcs", 1),
    "kapsul": ("pcs", 1),
    "caps": ("pcs", 1),
    "capsule": ("pcs", 1),
    "capsules": ("pcs", 1),
}

_NUMBER = r"\d+(?:[.,]\d+)*"
_SIZE_RE = re.compile(
    rf"(?<![\w.,])(?:(?P<count>\d{{1,2}})\s*[x×]\s*)?(?P<amount>{_NUMBER})\s*"
    rf"(?P<unit>{'|'.join(sorted(_UNITS, key=len, reverse=True))})"
    r"(?!\w)",  # \w covers Turkish letters too, so "1 Lip" or "50 gece" don't match
    re.IGNORECASE,
)

MAX_AMOUNT = 1_000_000  # 1000 L or 1000 kg; anything bigger is a misread


@dataclass(frozen=True)
class Size:
    amount: float
    unit: SizeUnit


def parse_size(text: str | None) -> Size | None:
    """The first pack size in ``text``, or None.

    "Şampuan 1,5 L" -> 1500 ml, "2 x 250 ml" -> 500 ml, "60 adet" -> 60 pieces.
    """
    if not text:
        return None
    for match in _SIZE_RE.finditer(text):
        amount = parse_price(match["amount"])
        if not amount:
            continue
        unit, factor = _UNITS[match["unit"].lower()]
        total = round(amount * factor * int(match["count"] or 1), 3)
        if 0 < total <= MAX_AMOUNT:
            return Size(total, unit)
    return None
