"""Turn raw price history into the numbers the dashboard and alerts need."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

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
