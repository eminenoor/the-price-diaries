"""Best time to buy: explainable patterns, and a backtest with no lookahead."""

import random
from datetime import date, datetime, timedelta

import pytest

from price_diaries.analysis import Reading
from price_diaries.demo import DEMO_PRODUCTS, DEMO_TODAY, demo_checks
from price_diaries.timing import (
    Backtest,
    backtest,
    best_time,
    cheap_month_runs,
    daily,
    real_sales,
    yearly_events,
)

START = date(2026, 5, 1)


def readings(prices: list[float], start: date = START) -> list[Reading]:
    """One check a day from ``start``, at 09:17."""
    return [
        Reading(datetime.combine(start + timedelta(days=i), datetime.min.time()), p)
        for i, p in enumerate(prices)
    ]


def priced(days: int, price, start: date = START) -> list[Reading]:
    """``price(day)`` for each day."""
    return readings([price(start + timedelta(days=i)) for i in range(days)], start)


def payday(day: date) -> float:
    return 90.0 if day.day in (1, 2, 15, 16) else 100.0


def sales_every(gap: int, price: float = 80.0, offset: int = 10):
    """A two-day real sale every ``gap`` days. Further apart than 14 days, a sale isn't
    taken for the "discount" after a rise from the sale before."""
    return lambda d: price if (d - START).days % gap in (offset, offset + 1) else None


# --- the days, compared only with the days before them --------------------------------------


def test_each_day_is_compared_only_with_the_days_before_it():
    rng = random.Random(1)
    history = priced(200, lambda d: payday(d) * rng.uniform(0.9, 1.1))
    full = daily(history)
    for cut in (10, 40, 90, 150, 199):
        assert daily(history[:cut]) == full[:cut]


def test_a_real_sale_is_5_percent_under_the_usual_price():
    days = daily(readings([100.0] * 30 + [96.0, 95.0, 100.0, 100.0]))
    assert [d.sale for d in days[-4:]] == [False, True, False, False]
    assert days[0].ratio is None  # nothing before it to compare with


def test_a_fake_sale_is_not_a_real_sale():
    # The regular price was 130, then 100 for a week; raised to 140, then "down" to 100.
    days = daily(readings([130.0] * 40 + [100.0] * 8 + [140.0] * 3 + [100.0]))
    assert days[-1].ratio is not None and days[-1].ratio <= 0.95  # cheap next to the usual
    assert not days[-1].sale  # but only after a rise: not really cheaper
    # A whole history of raised-then-"discounted" prices has no real sales at all.
    tricks = [125.0 if i % 20 in (10, 11, 12) else 100.0 for i in range(200)]
    assert real_sales(daily(readings(tricks))) == []
    assert not best_time(readings(tricks), START + timedelta(days=200)).enough_history


# --- not enough history -----------------------------------------------------------------------


def test_under_60_days_is_not_enough_history():
    sale = sales_every(16)
    history = priced(55, lambda d: sale(d) or 100.0)
    assert len(real_sales(daily(history))) >= 3
    assert best_time(history, START + timedelta(days=55)) == best_time([], START)
    assert not best_time(history, START + timedelta(days=55)).enough_history


def test_fewer_than_3_real_sales_is_not_enough_history():
    prices = [100.0] * 150
    prices[50:53] = [80.0] * 3
    prices[100:103] = [80.0] * 3
    assert len(real_sales(daily(readings(prices)))) == 2
    assert not best_time(readings(prices), START + timedelta(days=150)).enough_history


# --- the patterns -------------------------------------------------------------------------------


def test_cheaper_around_paydays_is_found_and_would_have_helped():
    found = best_time(priced(200, payday), START + timedelta(days=200))
    assert found.enough_history
    assert found.days_of_month == [1, 15]
    assert found.backtest is not None and found.backtest.helped
    assert found.weekdays == []


def test_a_month_end_run_goes_round_to_the_start_and_is_too_long_to_tell():
    month_end = priced(200, lambda d: 90.0 if d.day >= 30 or d.day <= 3 else 100.0)
    assert cheap_month_runs(daily(month_end)) == []


def test_cheaper_on_a_weekday_is_found():
    # A dip every week is a fake sale by the app's rule (back to the price of a week ago,
    # after a "rise"), so a few real sales make the history long enough.
    sale = sales_every(40, offset=12)
    found = best_time(
        priced(200, lambda d: sale(d) or (92.0 if d.weekday() == 0 else 100.0)), START
    )
    assert found.weekdays == [0]
    assert found.days_of_month == []


def test_regular_real_sales_give_their_gap_and_depth():
    found = best_time(
        priced(200, lambda d: 85.0 if (d - START).days % 35 < 4 else 100.0),
        START + timedelta(days=210),
    )
    assert found.cycle is not None
    assert found.cycle.every_days == 35 and round(found.cycle.depth, 2) == 0.15
    assert found.last_sale_days_ago == 210 - 175
    assert found.backtest is not None and found.backtest.helped


def test_efsane_cuma_is_found_with_its_discount():
    friday = yearly_events(2026)["Efsane Cuma"]
    assert friday == (date(2026, 11, 26), date(2026, 11, 29))

    def price(d: date) -> float:
        if friday[0] <= d <= friday[1]:
            return 80.0
        return 90.0 if (d - START).days % 50 < 3 else 100.0  # a few real sales too

    found = best_time(priced(214, price, date(2026, 5, 1)), date(2026, 12, 1))
    assert found.events == {"Efsane Cuma": pytest.approx(0.2)}


@pytest.mark.parametrize("seed", range(5))
def test_prices_that_move_at_random_show_no_day_pattern(seed):
    """Only a pattern that would have helped is shown: noise doesn't make one."""
    rng = random.Random(seed)
    found = best_time(
        priced(200, lambda d: 100.0 * (0.85 if rng.random() < 0.1 else rng.uniform(0.97, 1.03))),
        START + timedelta(days=200),
    )
    assert found.enough_history
    assert found.days_of_month == [] and found.weekdays == []


# --- the backtest -----------------------------------------------------------------------------


def next_day(before, today):
    return today + timedelta(days=1), today + timedelta(days=1)


def test_the_backtest_compares_waiting_with_buying_that_day():
    falling = daily(readings([200.0 - i for i in range(100)]))
    result = backtest(falling, next_day)
    # Only days with 60 days before them, and with a next day to wait for.
    assert result.trials == 39 and result.wins == 39 and result.average_saving > 0

    rising = backtest(daily(readings([100.0 + i for i in range(100)])), next_day)
    assert rising.wins == 0 and rising.average_saving < 0 and not rising.helped


def test_the_backtest_fits_each_day_on_the_days_before_it_only():
    seen = []

    def spy(before, today):
        seen.append((today, max(d.day for d in before)))
        return None

    backtest(daily(priced(100, payday)), spy)
    assert seen and all(last < today for today, last in seen)


def test_a_pattern_helps_only_with_enough_trials_mostly_wins_and_a_saving():
    assert Backtest(40, 24, 0.05, occasions=5, hits=3).helped
    assert not Backtest(9, 9, 0.05, occasions=5, hits=5).helped  # too few days to tell
    assert not Backtest(40, 23, 0.05, occasions=5, hits=5).helped  # paid less under 60%
    assert not Backtest(40, 30, 0.015, occasions=5, hits=5).helped  # under 2% saved
    # A pattern found in the history must have come true on most of its times: here many
    # days waited for the same two lucky days.
    assert not Backtest(40, 30, 0.05, occasions=2, hits=2).helped
    assert not Backtest(40, 30, 0.05, occasions=5, hits=2).helped
    # A calendar event isn't found in the history, so one past event can show it.
    assert Backtest(30, 27, 0.15, occasions=1, hits=1, fitted=False).helped


# --- on the product page -------------------------------------------------------------------------


def test_the_product_page_says_when_it_has_been_cheapest(demo_client):
    products = {p["listing_name"]: p for p in demo_client.get("/api/products").json()}

    def best(name: str) -> dict:
        return demo_client.get(f"/api/products/{products[name]['id']}").json()["best_time"]

    magnesium = best("Magnesium Bisglycinate 120 caps")
    assert magnesium["enough_history"] and magnesium["days_of_month"] == [1, 15]
    assert magnesium["backtest"]["wins"] > magnesium["backtest"]["trials"] / 2
    assert best("Vitamin D3 1000 IU, 90 tablets")["sale_cycle"]["last_days_ago"] == 5
    assert {"name": "Efsane Cuma", "pct": 32.4} in best("AHA BHA PHA 30 Days Miracle Toner 150 ml")[
        "events"
    ]
    assert best("Rice Water Bright Cleansing Foam 150 ml") == {
        "enough_history": False,
        "days_of_month": [],
        "weekdays": [],
        "sale_cycle": None,
        "events": [],
        "backtest": None,
    }


# --- on the demo data ---------------------------------------------------------------------------


def demo_best_times() -> dict[str, object]:
    found = {}
    for item in DEMO_PRODUCTS:
        history = [
            Reading(c.at, c.member_price or c.price, c.in_stock)
            for c in demo_checks(item)
            if c.price is not None
        ]
        found[item.name] = best_time(history, DEMO_TODAY)
    return found


def test_the_backtest_on_the_demo_data():
    found = demo_best_times()
    shown = {name: f for name, f in found.items() if f.backtest is not None}
    # Every pattern shown would have helped: mostly less, and less on average.
    for name, f in shown.items():
        assert f.backtest.wins >= 0.6 * f.backtest.trials, name
        assert f.backtest.average_saving >= 0.02, name
    assert len(shown) >= 10

    assert found["Magnesium Bisglycinate 120 caps"].days_of_month == [1, 15]  # paydays
    assert "Efsane Cuma" in found["AHA BHA PHA 30 Days Miracle Toner 150 ml"].events
    assert any(f.cycle is not None for f in found.values())
    assert not found["Centella Calming Cream 50 ml"].enough_history  # tracked since yesterday
    # With enough history, some products have no pattern that would have helped.
    assert any(f.enough_history and f.backtest is None for f in found.values())
