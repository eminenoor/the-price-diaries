"""The Sunday paper: the weekly numbers, always with fixed dates."""

from datetime import date, datetime, timedelta

import pytest

from price_diaries.analysis import (
    Reading,
    WeekFakeSale,
    WeekLow,
    WeekMove,
    paper_week,
    week_start,
    week_story,
)
from price_diaries.db import CheckFailure, Notification, PricePoint, Product
from price_diaries.demo import seed_demo
from price_diaries.paper import build_paper, paper_note_text, publish_paper, week_words
from tests.conftest import FakeDesktop

# The week of Monday 9 to Sunday 15 November 2026.
MONDAY = date(2026, 11, 9)
SUNDAY = date(2026, 11, 15)


def at(day: date, hour: int = 9, minute: int = 17) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute)


def daily(first: date, *prices: float, out_of_stock: tuple[int, ...] = ()) -> list[Reading]:
    """One check a day from ``first``, at 09:17."""
    return [
        Reading(at(first + timedelta(days=i)), p, i not in out_of_stock)
        for i, p in enumerate(prices)
    ]


# --- which week ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "monday"),
    [
        (date(2026, 11, 9), date(2026, 11, 9)),  # Monday
        (date(2026, 11, 12), date(2026, 11, 9)),
        (date(2026, 11, 15), date(2026, 11, 9)),  # Sunday
        (date(2026, 11, 16), date(2026, 11, 16)),
        (date(2027, 1, 1), date(2026, 12, 28)),  # across the new year
    ],
)
def test_a_week_starts_on_monday(day, monday):
    assert week_start(day) == monday


def test_the_latest_paper_is_out_on_sunday_morning():
    assert paper_week(date(2026, 11, 15)) == MONDAY  # Sunday: this week's
    assert paper_week(date(2026, 11, 16)) == MONDAY  # Monday: still last week's
    assert paper_week(date(2026, 11, 21)) == MONDAY  # Saturday: still last week's
    assert paper_week(date(2026, 11, 22)) == date(2026, 11, 16)


def test_the_week_in_words():
    assert week_words(MONDAY) == "9 to 15 Nov"
    assert week_words(date(2026, 10, 26)) == "26 Oct to 1 Nov"
    assert week_words(date(2026, 12, 28)) == "28 Dec to 3 Jan"


# --- one product's week ------------------------------------------------------------------------


def test_a_drop_compares_the_price_before_the_week_with_its_last_price():
    # Sat 7 and Sun 8 before the week, then Monday to Sunday.
    story = week_story(
        daily(date(2026, 11, 7), 400, 400, 400, 380, 360, 360, 352, 352, 352), MONDAY
    )
    assert story.move == WeekMove(400, 352, -12.0)
    assert story.checked


def test_a_rise_is_a_move_up():
    story = week_story(daily(date(2026, 11, 8), 159, 159, 159, 163.77), MONDAY)
    assert story.move == WeekMove(159, 163.77, 3.0)


def test_a_price_that_came_back_hasnt_moved():
    story = week_story(daily(date(2026, 11, 8), 300, 250, 250, 300), MONDAY)
    assert story.move is None


def test_a_few_kurus_isnt_news():
    # Under ₺1, and under 1% of ₺300.
    assert week_story(daily(date(2026, 11, 8), 300, 299.5), MONDAY).move is None
    assert week_story(daily(date(2026, 11, 8), 300, 297.01), MONDAY).move is None
    assert week_story(daily(date(2026, 11, 8), 300, 297), MONDAY).move is not None


def test_a_new_low_beats_every_price_before_the_week():
    readings = daily(date(2026, 11, 1), 300, 280, 300, 300, 300, 300, 300, 300, 290, 270, 275)
    story = week_story(readings, MONDAY)
    assert story.new_low == WeekLow(270, at(date(2026, 11, 10)), 280)


def test_no_new_low_when_it_only_matches_the_old_low():
    readings = daily(date(2026, 11, 1), 300, 280, 300, 300, 300, 300, 300, 300, 280)
    assert week_story(readings, MONDAY).new_low is None


def test_a_product_first_checked_this_week_has_no_news_yet():
    story = week_story(daily(date(2026, 11, 10), 300, 200, 100), MONDAY)
    assert story == week_story([], MONDAY).__class__(checked=True)


def test_a_fake_sale_is_news_in_the_week_it_was_caught():
    # Raised 25% on Thu 5 Nov, "discounted" back on Mon 9 Nov.
    readings = daily(date(2026, 11, 2), 100, 100, 100, 125, 125, 125, 125, 100, 100, 100)
    assert week_story(readings, MONDAY).fake_sale == WeekFakeSale(100, 125, at(MONDAY))
    # The next week, the same fake sale is still on, but it isn't news any more.
    later = [*readings, *daily(date(2026, 11, 12), *[100] * 7)]
    assert week_story(later, date(2026, 11, 16)).fake_sale is None


def test_a_fake_sale_isnt_a_drop():
    # Raised before the week, "discounted" on Monday: down 20% from Sunday, but not cheaper.
    readings = daily(date(2026, 11, 2), 100, 100, 100, 125, 125, 125, 125, 100)
    story = week_story(readings, MONDAY)
    assert story.fake_sale is not None
    assert story.move is None


def test_a_real_sale_isnt_a_fake_one():
    readings = daily(date(2026, 11, 2), 100, 100, 100, 125, 125, 125, 125, 80)
    assert week_story(readings, MONDAY).fake_sale is None


def test_out_of_stock_is_news_when_it_runs_out_this_week():
    readings = daily(date(2026, 11, 7), 100, 100, 100, 100, 100, 100, out_of_stock=(4, 5))
    assert week_story(readings, MONDAY).out_of_stock_at == at(date(2026, 11, 11))
    # Already out of stock before the week: not news.
    readings = daily(date(2026, 11, 7), 100, 100, 100, 100, out_of_stock=(1, 2, 3))
    assert week_story(readings, MONDAY).out_of_stock_at is None


def test_checks_outside_the_week_dont_count():
    story = week_story(daily(date(2026, 11, 16), 100, 50), MONDAY)
    assert story == story.__class__()
    assert not story.checked


# --- the whole paper -------------------------------------------------------------------------


def add_product(session, name: str, store: str = "gratis") -> Product:
    product = Product(url=f"https://www.{store}.com/{name}", name=name, store=store)
    session.add(product)
    session.flush()
    return product


def add_prices(session, product: Product, first: date, *prices: float, stock=()) -> None:
    for i, price in enumerate(prices):
        session.add(
            PricePoint(
                product_id=product.id,
                price=price,
                in_stock=i not in stock,
                checked_at=at(first + timedelta(days=i)),
            )
        )


def paper(session, monday: date = MONDAY, today: date = date(2026, 11, 17)):
    return build_paper(session, monday, True, today, lambda p: p.name)


def test_a_full_week_in_every_section(client):
    with client.app.state.db.session() as session:
        serum = add_product(session, "Serum")
        add_prices(session, serum, date(2026, 11, 1), *[400] * 8, 380, 352, 352)
        cream = add_product(session, "Cream", "watsons")
        add_prices(session, cream, date(2026, 11, 8), 200, 200, 230)
        toner = add_product(session, "Toner")
        add_prices(session, toner, date(2026, 11, 8), 100, 100, 100, 100, stock=(3,))
        sunscreen = add_product(session, "Sunscreen")
        add_prices(session, sunscreen, date(2026, 11, 2), 100, 100, 100, 125, 125, 125, 125, 100)
        session.add_all(
            [
                CheckFailure(
                    product_id=cream.id, error="Store answered 404.", checked_at=at(SUNDAY)
                ),
                CheckFailure(
                    product_id=cream.id, error="Store answered 500.", checked_at=at(SUNDAY, 10)
                ),
                # Outside the week: not counted.
                CheckFailure(product_id=toner.id, error="x", checked_at=at(date(2026, 11, 16))),
                Notification(
                    product_id=serum.id,
                    kind="cheaper",
                    old_price=352,
                    new_price=330,
                    other_store="watsons",
                    created_at=at(date(2026, 11, 13)),
                ),
            ]
        )
        session.commit()

        week = paper(session)

    assert (week.week_start, week.week_end) == (MONDAY, SUNDAY)
    assert week.products_checked == 4
    assert [(m.name, m.old_price, m.new_price, m.change_pct) for m in week.drops] == [
        ("Serum", 400, 352, -12.0)
    ]
    assert [(m.name, m.store_name, m.change_pct) for m in week.rises] == [
        ("Cream", "Watsons", 15.0)
    ]
    assert [(low.name, low.price, low.previous_low) for low in week.new_lows] == [
        ("Serum", 352, 400)
    ]
    assert [(f.name, f.price, f.peak) for f in week.fake_sales] == [("Sunscreen", 100, 125)]
    assert [(c.name, c.other_store_name, c.price_here, c.price_there) for c in week.cheaper] == [
        ("Serum", "Watsons", 352, 330)
    ]
    trouble = {t.name: t for t in week.trouble}
    assert trouble["Cream"].failed_checks == 2
    assert trouble["Cream"].last_error == "Store answered 500."
    assert trouble["Cream"].out_of_stock_at is None
    assert trouble["Toner"].failed_checks == 0
    assert trouble["Toner"].out_of_stock_at == at(date(2026, 11, 11))


def test_a_quiet_week_has_empty_sections(client):
    with client.app.state.db.session() as session:
        add_prices(session, add_product(session, "Toner"), date(2026, 11, 1), *[100] * 15)
        session.commit()
        week = paper(session)
    assert week.products_checked == 1
    sections = [week.drops, week.new_lows, week.fake_sales, week.cheaper, week.rises]
    assert all(section == [] for section in [*sections, week.trouble])


def test_previous_and_next_week(client):
    with client.app.state.db.session() as session:
        add_prices(session, add_product(session, "Toner"), date(2026, 11, 4), *[100] * 10)
        session.commit()
        # The first check was in the week before: you can go back one week, no further.
        assert paper(session).previous_week == date(2026, 11, 2)
        assert paper(session, date(2026, 11, 2)).previous_week is None
        # On Tuesday 17 Nov, this paper is the latest; on Sunday 22 Nov, the next is out.
        assert paper(session).next_week is None
        assert paper(session, today=date(2026, 11, 22)).next_week == date(2026, 11, 16)


def test_the_api_opens_any_day_of_a_past_week(client):
    with client.app.state.db.session() as session:
        add_prices(session, add_product(session, "Toner"), date(2026, 11, 8), 100, 80)
        session.commit()
    week = client.get("/api/paper", params={"week": "2026-11-12"}).json()
    assert week["week_start"] == "2026-11-09" and week["week_end"] == "2026-11-15"
    assert week["drops"][0]["change_pct"] == -20.0


def test_the_api_has_no_paper_for_a_week_that_isnt_over(client):
    future = date.today() + timedelta(days=7)
    response = client.get("/api/paper", params={"week": future.isoformat()})
    assert response.status_code == 404
    assert response.json()["detail"] == "That week's paper isn't out yet."
    latest = client.get("/api/paper").json()
    assert latest["week_start"] == paper_week(date.today()).isoformat()


def test_a_failed_check_is_kept_for_the_paper(client, fake_pages):
    product = client.post(
        "/api/products", json={"url": "https://www.gratis.com/urun-p-1", "name": "Toner"}
    ).json()
    assert client.post(f"/api/products/{product['id']}/check").json()["ok"] is False
    with client.app.state.db.session() as session:
        week = paper(session, week_start(date.today()), date.today())
    assert [(t.name, t.failed_checks, t.last_error) for t in week.trouble] == [
        ("Toner", 1, "Store answered 404.")
    ]


# --- the Sunday note -------------------------------------------------------------------------


async def test_the_paper_is_pinned_and_shown_once_on_sunday(client, desktop):
    notifier = FakeDesktop()
    with client.app.state.db.session() as session:
        assert await publish_paper(session, notifier, at(date(2026, 11, 14))) is None  # Saturday
        note = await publish_paper(session, notifier, at(SUNDAY))
        assert note is not None and note.week == MONDAY
        assert await publish_paper(session, notifier, at(SUNDAY, 18)) is None  # once a week
        assert await publish_paper(session, notifier, at(date(2026, 11, 22))) is not None
    assert desktop.sent == [
        ("Your Sunday paper is ready", "The week of 9 to 15 Nov, on one page."),
        ("Your Sunday paper is ready", "The week of 16 to 22 Nov, on one page."),
    ]

    inbox = client.get("/api/notifications").json()
    assert [(n["kind"], n["week"], n["product_id"]) for n in inbox["notes"]] == [
        ("sunday_paper", "2026-11-16", None),
        ("sunday_paper", "2026-11-09", None),
    ]
    assert inbox["unread"] == 2


async def test_a_missed_sunday_sends_the_note_at_the_next_check_once(client, desktop):
    notifier = FakeDesktop()
    with client.app.state.db.session() as session:
        add_prices(session, add_product(session, "Toner"), MONDAY, *[100] * 9)  # to Tue 17
        session.commit()
        # The app didn't run on Sunday 15 Nov. Tuesday's check sends last week's paper.
        note = await publish_paper(session, notifier, at(date(2026, 11, 17)))
        assert note is not None and note.week == MONDAY
        assert note.created_at == at(date(2026, 11, 17))
        # Once: not again on Wednesday, nor on Saturday.
        assert await publish_paper(session, notifier, at(date(2026, 11, 18))) is None
        assert await publish_paper(session, notifier, at(date(2026, 11, 21))) is None
        # Next Sunday brings that week's paper, as usual.
        assert (await publish_paper(session, notifier, at(date(2026, 11, 22)))).week == date(
            2026, 11, 16
        )
    assert desktop.sent == [
        ("Your Sunday paper is ready", "The week of 9 to 15 Nov, on one page."),
        ("Your Sunday paper is ready", "The week of 16 to 22 Nov, on one page."),
    ]


async def test_no_late_note_for_a_week_without_checks(client, desktop):
    # First started on Wednesday 18 Nov: the week before has nothing to report.
    with client.app.state.db.session() as session:
        add_prices(session, add_product(session, "Toner"), date(2026, 11, 18), 100)
        session.commit()
        assert await publish_paper(session, FakeDesktop(), at(date(2026, 11, 18))) is None
    assert desktop.sent == []


async def test_a_failing_desktop_doesnt_lose_the_note(client, desktop):
    desktop.fail = True
    with client.app.state.db.session() as session:
        assert await publish_paper(session, FakeDesktop(), at(SUNDAY)) is not None
    assert len(client.get("/api/notifications").json()["notes"]) == 1


def test_the_note_reads_like_the_desktop_notification():
    assert paper_note_text(MONDAY) == (
        "Your Sunday paper is ready",
        "The week of 9 to 15 Nov, on one page.",
    )


# --- the demo --------------------------------------------------------------------------------


@pytest.mark.parametrize("day", range(16, 23))  # Monday 16 to Sunday 22 November
def test_the_demo_fills_the_paper_on_any_day_of_the_week(client, day):
    today = date(2026, 11, day)
    with client.app.state.db.session() as session:
        seed_demo(session, now=at(today))
        week = paper(session, paper_week(today), today)
    for section in ("drops", "new_lows", "fake_sales", "cheaper", "rises", "trouble"):
        assert getattr(week, section), (today, section)
    # Today's states are still the scripted ones (see test_demo.py).
    products = {p["listing_name"]: p for p in client.get("/api/products").json()}
    assert products["Laundry Liquid 2.5 l"]["summary"]["fake_sale"]
    assert products["Vitamin C 15% Serum 30 ml"]["summary"]["is_all_time_low"]
    assert products["Gentle Foaming Cleanser 150 ml"]["summary"]["change_pct"] > 0
    assert products["Vitamin D3 1000 IU, 90 tablets"]["summary"]["change_pct"] == 0


def test_the_demo_fills_every_section_of_the_latest_paper(client):
    with client.app.state.db.session() as session:
        seed_demo(session)
    week = client.get("/api/paper").json()
    for section in ("drops", "new_lows", "fake_sales", "cheaper", "rises", "trouble"):
        assert week[section], section
    trouble = {t["name"]: t for t in week["trouble"]}
    assert trouble["Ceramide Barrier Cream 50 ml"]["failed_checks"] >= 2
    assert trouble["Vitamin D3 1000 IU, 90 tablets"]["out_of_stock_at"] is not None
    assert week["previous_week"] is not None and week["next_week"] is None
