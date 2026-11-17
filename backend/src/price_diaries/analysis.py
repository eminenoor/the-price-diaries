"""Turn raw price history into the numbers the dashboard and alerts need."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

History = list[tuple[datetime, float]]  # sorted oldest -> newest


@dataclass(frozen=True)
class PriceSummary:
    current: float
    previous: float | None
    lowest: float
    lowest_at: datetime
    highest: float
    highest_at: datetime
    lowest_30d: float
    change_pct: float | None  # vs previous reading
    is_all_time_low: bool
    fake_sale: bool


def summarize(history: History, now: datetime | None = None) -> PriceSummary | None:
    if not history:
        return None
    now = now or history[-1][0]
    current = history[-1][1]
    previous = history[-2][1] if len(history) > 1 else None

    low_at, low = min(history, key=lambda p: (p[1], p[0]))
    high_at, high = max(history, key=lambda p: (p[1], p[0]))
    last_30 = [p for t, p in history if t >= now - timedelta(days=30)] or [current]

    change = None
    if previous:
        change = round((current - previous) / previous * 100, 2)

    return PriceSummary(
        current=current,
        previous=previous,
        lowest=low,
        lowest_at=low_at,
        highest=high,
        highest_at=high_at,
        lowest_30d=min(last_30),
        change_pct=change,
        is_all_time_low=current <= low,
        fake_sale=is_fake_sale(history),
    )


@dataclass(frozen=True)
class Anomaly:
    checked_at: datetime
    price: float
    change_pct: float
    score: float  # modified z-score; |score| > threshold means unusual


def price_anomalies(
    history: History, threshold: float = 3.5, min_rise: float = 0.05
) -> list[Anomaly]:
    """Flag price *rises* that are unusual for this product.

    Rises are what matter here: an unusual rise is often the set-up for a
    fake "sale" a few days later. Drops are good news and shown elsewhere.

    Uses the modified z-score (Iglewicz & Hoaglin) of day-to-day log returns.
    It relies on the median and median absolute deviation (MAD) instead of
    mean and standard deviation, so the anomalies themselves don't distort
    the baseline. A product that changes price every day needs a much larger
    jump to be flagged than one whose price is usually stable.
    """
    if len(history) < 5:
        return []

    returns = [
        (history[i][0], history[i][1], math.log(history[i][1] / history[i - 1][1]))
        for i in range(1, len(history))
        if history[i - 1][1] > 0 and history[i][1] > 0
    ]
    values = [r for _, _, r in returns]
    median = statistics.median(values)
    mad = statistics.median(abs(r - median) for r in values)
    if mad == 0:
        # Price is usually flat: any real change is unusual. Use a small floor
        # so a 1 kuruş rounding change isn't reported as an anomaly.
        mad = 0.005

    anomalies = []
    for checked_at, price, r in returns:
        score = 0.6745 * (r - median) / mad
        if score > threshold and r >= math.log1p(min_rise):
            change = round((math.exp(r) - 1) * 100, 2)
            anomalies.append(Anomaly(checked_at, price, change, round(score, 2)))
    return anomalies


def is_fake_sale(
    history: History,
    window_days: int = 14,
    raise_threshold: float = 0.05,
    tolerance: float = 0.02,
) -> bool:
    """Detect the "raise it, then 'discount' it" pattern.

    Inside the last ``window_days``:
      1. the price rose by at least ``raise_threshold`` to a peak, and
      2. it has since dropped from that peak (looks like a sale), but
      3. the "sale" price is not really lower than before the raise
         (within ``tolerance``).
    """
    if len(history) < 3:
        return False

    latest_at, current = history[-1]
    window = [(t, p) for t, p in history if t >= latest_at - timedelta(days=window_days)]
    if len(window) < 3:
        return False

    peak_index = max(range(len(window)), key=lambda i: window[i][1])
    before_peak = window[:peak_index]
    if not before_peak or peak_index == len(window) - 1:
        return False  # no raise to compare against, or still at the peak

    peak = window[peak_index][1]
    base = min(p for _, p in before_peak)

    raised = peak >= base * (1 + raise_threshold)
    dropped = current < peak
    not_really_cheaper = current >= base * (1 - tolerance)
    return raised and dropped and not_really_cheaper


# How much of each unit the unit price is quoted for: "₺2,53 / 10 ml", "₺12,40 / 100 g",
# "₺8,30 / piece". Fixed per unit, so every product in that unit compares directly.
UNIT_BASIS: dict[str, int] = {"ml": 10, "g": 100, "pcs": 1}


@dataclass(frozen=True)
class UnitPrice:
    price: float  # for `per` of `unit`
    per: int
    unit: str


def unit_price(price: float, amount: float, unit: str) -> UnitPrice | None:
    """The price of ``UNIT_BASIS[unit]`` units, for a pack of ``amount`` units at ``price``."""
    per = UNIT_BASIS.get(unit)
    if per is None or amount <= 0 or price < 0:
        return None
    # Decimal, so a half kuruş rounds up the way a shop would (14,495 -> 14,50); float
    # rounding would give 14,49.
    exact = Decimal(str(price)) / Decimal(str(amount)) * per
    return UnitPrice(_kurus(exact), per, unit)


# --- the same product at other stores ----------------------------------------------

# Smaller differences aren't worth a note on the home page.
MIN_SAVING = 1.0


@dataclass(frozen=True)
class Offer:
    """One store's listing of a product, at the price you'd actually pay."""

    product_id: int
    price: float
    checked_at: datetime
    in_stock: bool = True
    size_amount: float | None = None
    size_unit: str | None = None


def _kurus(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), ROUND_HALF_UP))


def saving(here: Offer, there: Offer) -> float | None:
    """How much less ``there`` costs than ``here``, for the amount ``here`` sells.

    With both sizes known, ``there`` is scaled to ``here``'s pack size, so a 1,5 L
    bottle compares fairly with a 2,5 L one. Without both sizes the packs are
    assumed to match (they share a barcode or were linked by hand). Sizes in
    different units (ml against g) can't be compared: None. Negative means
    ``there`` costs more.
    """
    there_price = Decimal(str(there.price))
    if here.size_amount and there.size_amount:
        if here.size_unit != there.size_unit:
            return None
        there_price = there_price / Decimal(str(there.size_amount)) * Decimal(str(here.size_amount))
    return _kurus(Decimal(str(here.price)) - there_price)


def rank_offers(offers: list[Offer]) -> list[Offer]:
    """Cheapest first: by price per unit when every offer has a size in the same unit,
    otherwise by price. Ties go to the most recently checked."""
    units = {o.size_unit for o in offers}
    by_unit = len(units) == 1 and None not in units and all(o.size_amount for o in offers)

    def key(o: Offer) -> tuple[float, float]:
        price = o.price / o.size_amount if by_unit and o.size_amount else o.price
        return (price, -o.checked_at.timestamp())

    return sorted(offers, key=key)


def cheaper_elsewhere(here: Offer, others: list[Offer], today: date) -> tuple[Offer, float] | None:
    """The other store with the biggest saving today, if it saves at least ``MIN_SAVING``.

    Only listings checked today and in stock count: a price from last week, or one
    you can't buy, isn't a reason to shop elsewhere.
    """
    best: tuple[Offer, float] | None = None
    for there in others:
        if there.product_id == here.product_id or not there.in_stock:
            continue
        if there.checked_at.date() != today:
            continue
        amount = saving(here, there)
        if amount is None or amount < MIN_SAVING:
            continue
        if best is None or amount > best[1]:
            best = (there, amount)
    return best


# --- alerts ----------------------------------------------------------------------------

AlertKind = Literal["target", "lowest", "fake_sale", "cheaper", "back_in_stock"]
ALERT_KINDS: tuple[AlertKind, ...] = ("target", "lowest", "fake_sale", "cheaper", "back_in_stock")


@dataclass(frozen=True)
class Reading:
    """One check, at the price you'd actually pay."""

    checked_at: datetime
    price: float
    in_stock: bool = True


@dataclass(frozen=True)
class Signal:
    """Whether an alert's condition holds after the latest check, and the prices to report."""

    active: bool
    old_price: float | None = None
    new_price: float | None = None
    other_store: str | None = None


# A new lowest price is only worth a note when it's at least ₺1 and 1% below the low mark
# (see ``next_low_mark``), so a few kuruş of noise doesn't send one.
MIN_LOW_DROP = Decimal("1.00")
MIN_LOW_DROP_SHARE = Decimal("0.01")


def is_new_low(price: float, low_mark: float) -> bool:
    """``price`` beats ``low_mark`` by at least ₺1 and at least 1% (in exact kuruş)."""
    drop = Decimal(str(low_mark)) - Decimal(str(price))
    return drop >= MIN_LOW_DROP and drop >= Decimal(str(low_mark)) * MIN_LOW_DROP_SHARE


def next_low_mark(readings: list[Reading], low_mark: float | None, new_low: bool) -> float:
    """The price the next new-low note is measured from, after the latest of ``readings``.

    It's the price of the last new-low note, or, before the first one, the lowest price
    when notes started for this product. Small drops that don't send a note leave it
    where it is, so slow drops still add up to a note.
    """
    if low_mark is None:
        return min(r.price for r in readings)
    return readings[-1].price if new_low else low_mark


def alert_signals(
    readings: list[Reading],
    target: float | None,
    cheaper: tuple[str, float] | None = None,
    low_mark: float | None = None,
) -> dict[AlertKind, Signal]:
    """Every alert's condition after the latest of ``readings`` (oldest first, not empty).

    ``cheaper`` is the other store that sells it for less today and its price for this
    product's size (see ``cheaper_elsewhere``), or None. ``low_mark`` is what a new
    lowest price has to beat (see ``next_low_mark`` and ``is_new_low``); None (no mark
    yet) means no new-low note.
    """
    current = readings[-1]
    previous = readings[-2] if len(readings) > 1 else None
    old = previous.price if previous else None

    def signal(active: bool) -> Signal:
        return Signal(active, old, current.price) if active else Signal(False)

    return {
        # Out of stock isn't worth a note; when it's back, still under target, it is.
        "target": signal(
            target is not None and current.in_stock and round(current.price, 2) <= target
        ),
        "lowest": signal(low_mark is not None and is_new_low(current.price, low_mark)),
        "fake_sale": signal(is_fake_sale([(r.checked_at, r.price) for r in readings])),
        "cheaper": (
            Signal(True, current.price, cheaper[1], cheaper[0]) if cheaper else Signal(False)
        ),
        "back_in_stock": signal(
            previous is not None and current.in_stock and not previous.in_stock
        ),
    }


def fresh_alerts(
    signals: dict[AlertKind, Signal], previous: dict[AlertKind, bool], first_check: bool
) -> list[AlertKind]:
    """The alerts to send now: those whose condition just turned from false to true.

    A new lowest price is different: every one is its own event, so two drops in a row
    are two notes (the same low price again is never "new", so it can't repeat).

    Nothing on a product's first check, and nothing for an alert with no previous state
    (just after upgrading, say): its state is recorded, and only a later change counts.
    """
    if first_check:
        return []
    return [
        kind
        for kind in ALERT_KINDS
        if signals[kind].active
        and kind in previous
        and (kind == "lowest" or previous[kind] is False)
    ]


# --- the Sunday paper --------------------------------------------------------------------


def week_start(day: date) -> date:
    """The Monday of ``day``'s week."""
    return day - timedelta(days=day.weekday())


def paper_week(today: date) -> date:
    """The Monday of the latest week whose Sunday has come: this week on a Sunday (the
    paper comes out that morning), last week on any other day."""
    this_week = week_start(today)
    return this_week if today.weekday() == 6 else this_week - timedelta(days=7)


def noticeable(old: float, new: float) -> bool:
    """A change of at least ₺1 and at least 1% (in exact kuruş), the same bar as a new low."""
    if old <= 0:
        return False
    change = abs(Decimal(str(new)) - Decimal(str(old)))
    return change >= MIN_LOW_DROP and change >= Decimal(str(old)) * MIN_LOW_DROP_SHARE


@dataclass(frozen=True)
class WeekMove:
    """The price before the week against the price at its last check."""

    old_price: float
    new_price: float
    change_pct: float


@dataclass(frozen=True)
class WeekLow:
    price: float
    at: datetime
    previous_low: float


@dataclass(frozen=True)
class WeekFakeSale:
    """The check that first showed a fake sale, and the raised price before it."""

    price: float
    peak: float
    at: datetime


@dataclass(frozen=True)
class WeekStory:
    """What happened to one product in one week, from its checks."""

    move: WeekMove | None = None
    new_low: WeekLow | None = None
    fake_sale: WeekFakeSale | None = None
    out_of_stock_at: datetime | None = None
    checked: bool = False  # it was checked at least once that week


def week_story(readings: list[Reading], monday: date, fake_window_days: int = 14) -> WeekStory:
    """One product's week (``monday`` to Sunday), from all its readings, oldest first.

    - move: the price before the week against the last price in it, when the change is
      noticeable. A product first checked this week has nothing to compare with, and a
      drop that's a fake sale isn't a move.
    - new_low: the week's lowest price beats every price before the week by ₺1 and 1%.
    - fake_sale: a check this week turned the fake-sale rule on (it was off at the check
      before), so a fake sale that spans two weeks is only news in the first.
    - out_of_stock_at: the first check this week that was out of stock after one that wasn't.
    """
    end = monday + timedelta(days=7)
    before = [r for r in readings if r.checked_at.date() < monday]
    week = [i for i, r in enumerate(readings) if monday <= r.checked_at.date() < end]
    if not week:
        return WeekStory()
    in_week = [readings[i] for i in week]

    move = None
    if before:
        old, new = before[-1].price, in_week[-1].price
        if noticeable(old, new):
            move = WeekMove(old, new, round((new - old) / old * 100, 2))

    new_low = None
    if before:
        lowest = min(in_week, key=lambda r: (r.price, r.checked_at))
        previous_low = min(r.price for r in before)
        if is_new_low(lowest.price, previous_low):
            new_low = WeekLow(lowest.price, lowest.checked_at, previous_low)

    fake_sale = None
    history = [(r.checked_at, r.price) for r in readings]
    for i in week:
        if is_fake_sale(history[: i + 1]) and not (i > 0 and is_fake_sale(history[:i])):
            since = readings[i].checked_at - timedelta(days=fake_window_days)
            peak = max(r.price for r in readings[:i] if r.checked_at >= since)
            fake_sale = WeekFakeSale(readings[i].price, peak, readings[i].checked_at)
            break

    # A "drop" back from a raised price isn't one: it goes under fake sales only.
    if move and move.change_pct < 0 and (fake_sale or is_fake_sale(history[: week[-1] + 1])):
        move = None

    out_of_stock_at = next(
        (
            readings[i].checked_at
            for i in week
            if not readings[i].in_stock and i > 0 and readings[i - 1].in_stock
        ),
        None,
    )
    return WeekStory(move, new_low, fake_sale, out_of_stock_at, checked=True)


def pick_display_name(names: list[str]) -> str:
    """The most complete of several stores' names for one product.

    Most distinct words wins ("Some By Mi AHA BHA PHA Miracle Toner 150 ml" over
    "AHA BHA PHA Miracle Toner"), then the longer name, then the first one given.
    """

    def words(name: str) -> int:
        return len({w.strip(".,;:()-").casefold() for w in name.split()} - {""})

    return max(names, key=lambda n: (words(n), len(n), -names.index(n)))
