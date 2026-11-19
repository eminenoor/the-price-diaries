"""When a product has been cheapest, from its own price history, and whether waiting for
that time would really have paid off.

Nothing here is a black box. A day's "usual price" is the median of the 28 days before it;
a real sale is a day at least 5% under it that isn't a fake sale. The patterns are simple
averages of that: days of the month and of the week that have been cheaper, the gap between
real sales, and how the product did at yearly events (11.11 and Efsane Cuma).

A pattern is only worth telling if it would have helped. ``backtest`` replays the history:
on each past day it fits the pattern from the days *before* it only, waits for the time
the pattern suggests, and compares the lowest price then with that day's price. A pattern
is shown only when waiting paid less more often than not, and less on average.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from price_diaries.analysis import Reading, is_fake_sale

MIN_HISTORY_DAYS = 60  # fewer days than this: "Not enough history yet"
MIN_REAL_SALES = 3
USUAL_DAYS = 28  # a day's usual price is the median of this many days before it
SALE_SHARE = 0.05  # a real sale is at least 5% under the usual price
CHEAPER_BY = 0.02  # a day of the month (or week) counts when 2% cheaper than average
MIN_TRIALS = 10  # a backtest needs this many past days to say anything


@dataclass(frozen=True)
class Day:
    """One day's price, compared with the days before it (never after)."""

    day: date
    price: float
    ratio: float | None  # price / usual price before it; None without enough days before
    sale: bool  # a real sale: 5% under the usual price, and not a fake sale


@dataclass(frozen=True)
class Sale:
    start: date
    end: date
    depth: float  # the deepest share off the usual price


Window = tuple[date, date]
Rule = Callable[[Sequence[Day], date], Window | None]
EventName = Literal["11.11", "Efsane Cuma"]
EVENTS: tuple[EventName, ...] = ("11.11", "Efsane Cuma")


def daily(readings: Sequence[Reading]) -> list[Day]:
    """One in-stock price a day (the day's last), each compared with the days before it.

    Every value uses only earlier readings, so ``daily(r[:k])`` is ``daily(r)[:k]``: there
    is no lookahead anywhere below.
    """
    last: dict[date, Reading] = {}
    for r in readings:
        if r.in_stock:
            last[r.checked_at.date()] = r
    ordered = [last[d] for d in sorted(last)]
    history = [(r.checked_at, r.price) for r in ordered]
    days: list[Day] = []
    for i, r in enumerate(ordered):
        day = r.checked_at.date()
        before = [d.price for d in days if day - timedelta(days=USUAL_DAYS) <= d.day < day]
        ratio = r.price / statistics.median(before) if len(before) >= 7 else None
        sale = ratio is not None and ratio <= 1 - SALE_SHARE
        if sale and is_fake_sale(history[: i + 1]):
            sale = False
        days.append(Day(day, r.price, ratio, sale))
    return days


def real_sales(days: Sequence[Day]) -> list[Sale]:
    """Runs of real-sale days; a gap of up to two days (a missed check) doesn't end one."""
    sales: list[Sale] = []
    for d in days:
        if not d.sale or d.ratio is None:
            continue
        depth = 1 - d.ratio
        if sales and (d.day - sales[-1].end).days <= 3:
            last = sales[-1]
            sales[-1] = Sale(last.start, d.day, max(last.depth, depth))
        else:
            sales.append(Sale(d.day, d.day, depth))
    return sales


# --- the patterns ------------------------------------------------------------------------


def in_yearly_event(day: date) -> bool:
    return any(start <= day <= end for start, end in yearly_events(day.year).values())


def _slot_ratios(days: Sequence[Day], slot: Callable[[date], int]) -> dict[int, list[float]]:
    """Each slot's ratios. Yearly events are left out: they're a pattern of their own, and
    Efsane Cuma would otherwise make the last days of every month look cheap."""
    seen: dict[int, list[float]] = {}
    for d in days:
        if d.ratio is not None and not in_yearly_event(d.day):
            seen.setdefault(slot(d.day), []).append(d.ratio)
    return seen


def _cheaper_slots(
    days: Sequence[Day], slot: Callable[[date], int], min_seen: int
) -> dict[int, float]:
    """Slots (days of the month, or of the week) whose median ratio is at least
    ``CHEAPER_BY`` under the median of all days, with their median ratio. Medians, so a
    habit counts and one big sale that happened to fall on a day doesn't."""
    seen = _slot_ratios(days, slot)
    every = [r for ratios in seen.values() for r in ratios]
    if not every:
        return {}
    usual = statistics.median(every)
    medians = {s: statistics.median(r) for s, r in seen.items() if len(r) >= min_seen}
    return {s: m for s, m in medians.items() if m <= usual - CHEAPER_BY}


def cheap_days_of_month(days: Sequence[Day]) -> list[int]:
    return sorted(day for run in cheap_month_runs(days) for day in run)


def cheap_month_runs(days: Sequence[Day]) -> list[list[int]]:
    """The cheaper days of the month: at most two runs of up to three neighbouring days (the
    cheapest runs), in month order. A longer run isn't "around" a day, so it doesn't count."""
    cheap = _cheaper_slots(days, lambda d: d.day, min_seen=3)
    runs: list[list[int]] = []
    for day in sorted(cheap):
        if runs and day == runs[-1][-1] + 1:
            runs[-1].append(day)
        else:
            runs.append([day])
    if len(runs) > 1 and runs[0][0] == 1 and runs[-1][-1] >= 30:  # the 30th/31st to the 2nd
        runs[0] = runs.pop() + runs[0]
    runs = sorted((r for r in runs if len(r) <= 3), key=lambda r: min(cheap[d] for d in r))
    return sorted(runs[:2], key=lambda r: r[0])


def cheap_weekdays(days: Sequence[Day]) -> list[int]:
    """The cheaper days of the week (Monday is 0), at most two."""
    cheap = _cheaper_slots(days, lambda d: d.weekday(), min_seen=4)
    return sorted(sorted(cheap, key=lambda w: cheap[w])[:2])


@dataclass(frozen=True)
class Cycle:
    every_days: int  # the median gap between the starts of real sales
    depth: float  # the median depth of a real sale
    last_start: date


def sale_cycle(days: Sequence[Day]) -> Cycle | None:
    sales = real_sales(days)
    if len(sales) < MIN_REAL_SALES:
        return None
    gaps = [(b.start - a.start).days for a, b in zip(sales, sales[1:], strict=False)]
    return Cycle(
        round(statistics.median(gaps)),
        statistics.median(s.depth for s in sales),
        sales[-1].start,
    )


def yearly_events(year: int) -> dict[EventName, Window]:
    """11.11 (the day either side) and Efsane Cuma (the last Friday of November, Thursday
    to Sunday), in ``year``."""
    friday = date(year, 11, 30)
    while friday.weekday() != 4:
        friday -= timedelta(days=1)
    return {
        "11.11": (date(year, 11, 10), date(year, 11, 12)),
        "Efsane Cuma": (friday - timedelta(days=1), friday + timedelta(days=2)),
    }


def event_depth(days: Sequence[Day], window: Window) -> float | None:
    """The deepest share off the usual price during an event, or None if no checks then."""
    ratios = [d.ratio for d in days if window[0] <= d.day <= window[1] and d.ratio is not None]
    return max(0.0, 1 - min(ratios)) if ratios else None


# --- what each pattern suggests on a day, from the days before it -------------------------


def _next_run(
    today: date, slots: set[int], slot: Callable[[date], int], within: int
) -> Window | None:
    for ahead in range(1, within + 1):
        start = today + timedelta(days=ahead)
        if slot(start) in slots:
            end = start
            while slot(end + timedelta(days=1)) in slots and end < start + timedelta(days=6):
                end += timedelta(days=1)
            return start, end
    return None


def days_of_month_rule(before: Sequence[Day], today: date) -> Window | None:
    slots = set(cheap_days_of_month(before))
    return _next_run(today, slots, lambda d: d.day, 31) if slots else None


def weekdays_rule(before: Sequence[Day], today: date) -> Window | None:
    slots = set(cheap_weekdays(before))
    return _next_run(today, slots, lambda d: d.weekday(), 7) if slots else None


def cycle_rule(before: Sequence[Day], today: date) -> Window | None:
    """Wait for the next real sale, due a usual gap after the last one (soon, if overdue)."""
    cycle = sale_cycle(before)
    if cycle is None:
        return None
    due = cycle.last_start + timedelta(days=cycle.every_days)
    if due <= today:
        return today + timedelta(days=1), today + timedelta(days=7)
    if (due - today).days > 45:
        return None
    return due, due + timedelta(days=4)


def event_rule(name: EventName) -> Rule:
    """Wait for the event's day (11 November; Efsane Cuma's Friday) when it's at most 30
    days away."""

    def rule(before: Sequence[Day], today: date) -> Window | None:
        for year in (today.year, today.year + 1):
            start, end = yearly_events(year)[name]
            day = start + timedelta(days=1)  # the 11th, or the Friday
            if 1 <= (day - today).days <= 30:
                return day, end
        return None

    return rule


def earliest(rules: Sequence[Rule]) -> Rule:
    """All the shown patterns together: wait for whichever time comes first."""

    def rule(before: Sequence[Day], today: date) -> Window | None:
        windows = [w for r in rules if (w := r(before, today)) is not None]
        return min(windows) if windows else None

    return rule


# --- the backtest ------------------------------------------------------------------------


HIT_RATIO = 0.97  # a suggested time was really cheap: 3% under the usual price
MIN_OCCASIONS = 3  # a pattern fitted on the history must have come true this many times


@dataclass(frozen=True)
class Backtest:
    trials: int  # past days on which the pattern suggested waiting
    wins: int  # ...and waiting paid less than buying that day
    average_saving: float  # share saved by waiting, on average (negative: paid more)
    occasions: int = 0  # the different times waited for
    hits: int = 0  # ...that really were cheap (3% under the usual price)
    fitted: bool = True  # the pattern came from the history (a calendar event doesn't)

    @property
    def helped(self) -> bool:
        """Waiting paid less at least 60% of the time, and 2% less on average. A pattern
        found in the history must also have come true on most of the times it suggested:
        many days wait for the same time, so one lucky day could otherwise carry it."""
        consistent = not self.fitted or (
            self.occasions >= MIN_OCCASIONS and self.hits >= 0.6 * self.occasions
        )
        return (
            self.trials >= MIN_TRIALS
            and self.wins >= 0.6 * self.trials
            and self.average_saving >= 0.02
            and consistent
        )


def backtest(days: Sequence[Day], rule: Rule, fitted: bool = True) -> Backtest:
    """On every past day with ``MIN_HISTORY_DAYS`` before it, fit ``rule`` on the earlier
    days only and wait for the time it suggests. Then buy on the first real-sale day of
    that time, or on its last day: a choice made on the day, never with hindsight (the
    lowest price of the window would beat a single day's price even at random)."""
    savings: list[float] = []
    wins = 0
    occasions: dict[date, bool] = {}  # the day bought -> it was really cheap
    for i, today in enumerate(days):
        if (today.day - days[0].day).days < MIN_HISTORY_DAYS:
            continue
        window = rule(days[:i], today.day)
        if window is None:
            continue
        later = [d for d in days[i + 1 :] if window[0] <= d.day <= window[1]]
        if not later:  # the time hasn't come yet, or nothing was checked then
            continue
        bought = next((d for d in later if d.sale), later[-1])
        wins += bought.price < today.price
        savings.append((today.price - bought.price) / today.price)
        occasions[bought.day] = bought.ratio is not None and bought.ratio <= HIT_RATIO
    return Backtest(
        len(savings),
        wins,
        statistics.fmean(savings) if savings else 0.0,
        len(occasions),
        sum(occasions.values()),
        fitted,
    )


# --- the note -------------------------------------------------------------------------------


@dataclass(frozen=True)
class BestTime:
    """What the product page says. Only patterns that would have helped are filled in."""

    enough_history: bool
    days_of_month: list[int] = field(default_factory=list)  # the first day of each cheap run
    weekdays: list[int] = field(default_factory=list)
    cycle: Cycle | None = None
    last_sale_days_ago: int | None = None
    events: dict[EventName, float] = field(default_factory=dict)  # share off, the last time
    backtest: Backtest | None = None  # all the shown patterns together


def best_time(readings: Sequence[Reading], today: date) -> BestTime:
    days = daily(readings)
    if not days or (days[-1].day - days[0].day).days < MIN_HISTORY_DAYS:
        return BestTime(enough_history=False)
    if len(real_sales(days)) < MIN_REAL_SALES:
        return BestTime(enough_history=False)

    shown: list[Rule] = []
    month_days: list[int] = []
    weekdays: list[int] = []
    if backtest(days, days_of_month_rule).helped:
        shown.append(days_of_month_rule)
        month_days = [run[0] for run in cheap_month_runs(days)]
    if backtest(days, weekdays_rule).helped:
        shown.append(weekdays_rule)
        weekdays = cheap_weekdays(days)
    cycle = sale_cycle(days)
    if cycle and backtest(days, cycle_rule).helped:
        shown.append(cycle_rule)
    else:
        cycle = None
    events: dict[EventName, float] = {}
    for name in EVENTS:
        last = _last_depth(days, name)
        if last and backtest(days, event_rule(name), fitted=False).helped:
            shown.append(event_rule(name))
            events[name] = last
    return BestTime(
        enough_history=True,
        days_of_month=month_days,
        weekdays=weekdays,
        cycle=cycle,
        last_sale_days_ago=(today - cycle.last_start).days if cycle else None,
        events=events,
        backtest=backtest(days, earliest(shown)) if shown else None,
    )


def _last_depth(days: Sequence[Day], name: EventName) -> float | None:
    for year in range(days[-1].day.year, days[0].day.year - 1, -1):
        window = yearly_events(year)[name]
        if window[1] <= days[-1].day and (depth := event_depth(days, window)) is not None:
            return depth
    return None
