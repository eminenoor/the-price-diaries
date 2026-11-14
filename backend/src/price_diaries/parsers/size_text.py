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


def find_size(text: str | None) -> tuple[Size, int, int] | None:
    """The first pack size in ``text`` and where it is written (start, end), or None."""
    if not text:
        return None
    for match in _SIZE_RE.finditer(text):
        amount = parse_price(match["amount"])
        if not amount:
            continue
        unit, factor = _UNITS[match["unit"].lower()]
        total = round(amount * factor * int(match["count"] or 1), 3)
        if 0 < total <= MAX_AMOUNT:
            return Size(total, unit), match.start(), match.end()
    return None


def parse_size(text: str | None) -> Size | None:
    """The first pack size in ``text``, or None.

    "Şampuan 1,5 L" -> 1500 ml, "2 x 250 ml" -> 500 ml, "60 adet" -> 60 pieces.
    """
    found = find_size(text)
    return found[0] if found else None


def _written(size: Size) -> str:
    if size.unit == "pcs":
        return f"{size.amount:g} pcs"
    if size.amount >= 1000:
        return f"{size.amount / 1000:g} {'l' if size.unit == 'ml' else 'kg'}"
    return f"{size.amount:g} {size.unit}"


def with_size(name: str, size: Size | None, own_name: str = "") -> str:
    """``name`` with the pack size it mentions changed to ``size``.

    A group of stores shares one name, but a 1,5 L bottle mustn't be called "2,5 l".
    The size is written the way ``own_name`` (this store's name) writes it, if it does.
    Names without a size, or with the right one, are returned unchanged.
    """
    found = find_size(name)
    if size is None or found is None or found[0] == size:
        return name
    own = find_size(own_name)
    text = own_name[own[1] : own[2]] if own and own[0] == size else _written(size)
    return name[: found[1]] + text + name[found[2] :]
