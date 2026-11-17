import logging
from datetime import datetime, timedelta

import pytest
from desktop_notifier.backends.dummy import DummyNotificationCenter

from price_diaries import cli
from price_diaries.analysis import (
    Reading,
    Signal,
    alert_signals,
    fresh_alerts,
    is_new_low,
    next_low_mark,
)
from price_diaries.db import Notification, PricePoint, Product
from price_diaries.demo import DEMO_NOTES, seed_demo
from price_diaries.notifications import DesktopNotifications as RealDesktop
from price_diaries.notifications import detect, lira, note_text
from price_diaries.settings import Settings
from tests.conftest import FakeDesktop

TODAY = datetime.now().replace(hour=9, minute=17, second=0, microsecond=0)


# --- the alert rules (pure) ---------------------------------------------------------------


def readings(*prices: float, out_of_stock: tuple[int, ...] = ()) -> list[Reading]:
    start = TODAY - timedelta(days=len(prices) - 1)
    return [
        Reading(start + timedelta(days=i), p, i not in out_of_stock) for i, p in enumerate(prices)
    ]


def active(signals: dict) -> set[str]:
    return {kind for kind, s in signals.items() if s.active}


def test_target_needs_the_price_at_or_under_it_and_in_stock():
    assert "target" in active(alert_signals(readings(300, 250), target=250))
    assert "target" not in active(alert_signals(readings(300, 250.01), target=250))
    assert "target" not in active(alert_signals(readings(300, 240, out_of_stock=(1,)), 250))
    assert "target" not in active(alert_signals(readings(300, 100), target=None))


def test_lowest_is_measured_from_the_low_mark():
    signals = alert_signals(readings(300, 280, 260), target=None, low_mark=280)
    assert signals["lowest"] == Signal(True, 280, 260)
    assert "lowest" not in active(alert_signals(readings(300, 260, 260), None, low_mark=260))
    assert "lowest" not in active(alert_signals(readings(260), None))  # no mark yet
    # 0.1 + 0.2 isn't 0.3 in floats; in kuruş it's the same price.
    assert "lowest" not in active(alert_signals(readings(0.3, 0.1 + 0.2), None, low_mark=0.3))


def test_the_low_mark_moves_only_with_a_new_low_note():
    assert next_low_mark(readings(300, 280, 290), None, new_low=False) == 280  # the start
    assert next_low_mark(readings(300, 299), 300, new_low=False) == 300  # small drop: stays
    assert next_low_mark(readings(300, 290), 300, new_low=True) == 290  # a note: moves


def test_a_new_low_needs_at_least_one_lira_and_one_percent():
    # Cheap product: ₺1 is the bar (1% of ₺50 is only ₺0,50).
    assert is_new_low(49.00, 50.00)
    assert not is_new_low(49.01, 50.00)
    # Pricier product: 1% is the bar (₺1 of ₺300 is only 0,3%).
    assert is_new_low(297.00, 300.00)
    assert not is_new_low(297.01, 300.00)
    # Exactly at both bars at ₺100.
    assert is_new_low(99.00, 100.00)
    assert not is_new_low(99.50, 100.00)
    assert not is_new_low(100.00, 100.00)

    assert "lowest" not in active(alert_signals(readings(300, 299), None, low_mark=300))
    assert "lowest" in active(alert_signals(readings(300, 297), None, low_mark=300))


def test_fake_sale_uses_the_analysis_rule():
    raised = readings(100, 100, 100, 125, 125, 100)
    assert alert_signals(raised, None)["fake_sale"] == Signal(True, 125, 100)


def test_cheaper_reports_the_other_store_and_its_price_for_this_size():
    signals = alert_signals(readings(300), None, cheaper=("watsons", 260.0))
    assert signals["cheaper"] == Signal(True, 300, 260.0, "watsons")


def test_back_in_stock_after_a_check_out_of_stock():
    assert "back_in_stock" in active(alert_signals(readings(300, 300, out_of_stock=(0,)), None))
    assert "back_in_stock" not in active(alert_signals(readings(300, 300), None))


def test_fresh_alerts_only_when_turning_on():
    on = alert_signals(readings(300, 250), target=260, low_mark=300)
    assert fresh_alerts(on, {"target": False, "lowest": False}, first_check=False) == [
        "target",
        "lowest",
    ]
    # Still under the alert price: no repeat. A second drop in a row is a new low, though.
    assert fresh_alerts(on, {"target": True, "lowest": True}, first_check=False) == ["lowest"]
    assert fresh_alerts(on, {}, first_check=False) == []  # no state yet: only record it
    assert fresh_alerts(on, {"target": False}, first_check=True) == []


# --- detecting and remembering (database) ---------------------------------------------------


@pytest.fixture
def session(client):
    with client.app.state.db.session() as session:
        yield session


def add(session, *prices, target=None, store="gratis", group=None, size=None, start=None):
    product = Product(
        url=f"https://www.{store}.com/p-{len(prices)}-{target}-{group}-{id(prices)}",
        name="Toner",
        store=store,
        target_price=target,
        group_key=group,
        size_amount=size,
        size_unit="ml" if size else None,
    )
    session.add(product)
    session.flush()
    start = start or TODAY - timedelta(days=len(prices) - 1)
    for i, price in enumerate(prices):
        session.add(PricePoint(product_id=product.id, price=price, checked_at=start + timedelta(i)))
    session.commit()
    return product


def check(session, product, price, in_stock=True) -> list[str]:
    """A check: a new price today (or later), then the notes it brings."""
    last = product.prices[-1].checked_at if product.prices else TODAY
    session.add(
        PricePoint(
            product_id=product.id,
            price=price,
            in_stock=in_stock,
            checked_at=max(last + timedelta(minutes=1), TODAY),
        )
    )
    session.commit()
    return [n.kind for n in detect(session, [product], use_member=True)]


def test_target_note_only_again_after_going_above_and_back(session):
    product = add(session, 300, target=250)
    assert check(session, product, 300) == []  # records the state
    assert check(session, product, 240) == ["target", "lowest"]
    assert check(session, product, 240) == []  # still under: no repeat
    assert check(session, product, 245) == []
    assert check(session, product, 260) == []  # back above
    assert check(session, product, 249) == ["target"]  # and down again


def test_never_a_note_on_a_new_products_first_check(session):
    product = add(session, target=500)
    assert check(session, product, 100) == []
    # Its state was recorded, so the second check doesn't count as a change either.
    assert check(session, product, 90) == ["lowest"]


def test_products_from_before_notes_start_quietly(session):
    product = add(session, 300, 280, 260, target=270)  # no alert state yet
    assert detect(session, [product], use_member=True) == []
    assert check(session, product, 250) == ["lowest"]


def test_each_new_low_is_a_new_note(session):
    product = add(session, 300)
    check(session, product, 300)
    assert check(session, product, 280) == ["lowest"]
    assert check(session, product, 280) == []
    assert check(session, product, 270) == ["lowest"]
    assert check(session, product, 260) == ["lowest"]  # two drops in a row: two new lows


def test_a_few_kurus_below_the_lowest_isnt_a_note(session):
    product = add(session, 300)
    check(session, product, 300)
    assert check(session, product, 298.50) == []  # ₺1,50 but only 0,5% lower
    assert check(session, product, 295.00) == ["lowest"]  # ₺5 below the starting ₺300
    assert check(session, product, 294.50) == []  # measured from that note's ₺295 now


def test_slow_small_drops_add_up_to_a_note(session):
    """₺1 a day is never 1% of the day before, but three days of it is 1% of ₺300."""
    product = add(session, 300)
    check(session, product, 300)  # notes start: the mark is ₺300
    assert check(session, product, 299) == []
    assert check(session, product, 298) == []
    assert check(session, product, 297) == ["lowest"]  # ₺3 and 1% below ₺300
    # The next note is measured from ₺297, the price of this one.
    assert check(session, product, 296) == []
    assert check(session, product, 295) == []
    assert check(session, product, 294.03) == ["lowest"]  # 1% of ₺297 is ₺2,97


def test_the_starting_lowest_is_the_mark_before_any_note(session):
    product = add(session, 300, 280, 290)  # tracked before notes: lowest so far ₺280
    assert detect(session, [product], use_member=True) == []
    assert check(session, product, 278) == []  # ₺2 is under 1% of ₺280
    assert check(session, product, 277.20) == ["lowest"]  # exactly 1% below ₺280


def test_fake_sale_note(session):
    product = add(session, *[100] * 8, 125, 125, 125)
    check(session, product, 125)
    assert check(session, product, 100) == ["fake_sale"]
    assert check(session, product, 100) == []


def test_back_in_stock_note(session):
    product = add(session, 300)
    check(session, product, 300, in_stock=False)
    assert check(session, product, 300) == ["back_in_stock"]


def test_cheaper_at_another_store_compares_per_unit(session):
    here = add(session, 300, 300, size=150, group="gtin:1")
    # 100 ml for ₺180 is ₺270 for 150 ml: ₺30 less for the same amount.
    there = add(session, 200, store="watsons", size=100, group="gtin:1", start=TODAY)
    check(session, here, 300)
    assert check(session, there, 180) == []  # its first check doesn't count
    notes = detect(session, [here], use_member=True)
    assert [(n.kind, n.old_price, n.new_price, n.other_store) for n in notes] == [
        ("cheaper", 300, 270, "watsons")
    ]
    assert detect(session, [here], use_member=True) == []


def test_a_price_per_ml_that_isnt_cheaper_isnt_a_note(session):
    here = add(session, 300, 300, size=150, group="gtin:2")
    there = add(session, 210, 210, store="watsons", size=100, group="gtin:2")  # ₺315 / 150 ml
    check(session, here, 300)
    check(session, there, 210)
    assert detect(session, [here], use_member=True) == []


# --- text ------------------------------------------------------------------------------------


def test_lira_in_turkish_format():
    assert lira(1299.9) == "₺1.299,90"
    assert lira(14.495) == "₺14,50"
    assert lira(89) == "₺89,00"


def test_note_text_is_short_and_plain():
    note = Notification(kind="target", old_price=300, new_price=249.9)
    assert note_text(note, "Miracle Toner", "Gratis") == (
        "At your alert price",
        "Miracle Toner at Gratis is now ₺249,90 (was ₺300,00), at or under your alert price.",
    )
    cheaper = Notification(kind="cheaper", old_price=494, new_price=454, other_store="watsons")
    assert note_text(cheaper, "Miracle Toner", "Gratis")[1] == (
        "Miracle Toner is ₺454,00 at Watsons for the same amount, ₺494,00 at Gratis."
    )
    same = Notification(kind="back_in_stock", old_price=420, new_price=420)
    assert (
        note_text(same, "Coffee", "Amazon")[1] == "Coffee is back in stock at Amazon, now ₺420,00."
    )
    for kind in ("lowest", "fake_sale", "back_in_stock"):
        title, text = note_text(Notification(kind=kind, new_price=10), "Toner", "Gratis")
        assert title and "Toner" in text and "Gratis" in text and "₺10,00" in text


# --- through the API ---------------------------------------------------------------------------

URL = "https://www.gratis.com/serum-p-1"


def page(price: float) -> str:
    return (
        '<script type="application/ld+json">'
        f'{{"@type": "Product", "offers": {{"price": "{price}", "priceCurrency": "TRY"}}}}'
        "</script>"
    )


def test_checks_fill_the_inbox_and_show_desktop_notifications(client, fake_pages, desktop):
    product_id = client.post(
        "/api/products", json={"url": URL, "name": "Serum", "target_price": 250}
    ).json()["id"]
    for price in (300, 300, 240):
        fake_pages[URL] = page(price)
        assert client.post("/api/check").json()[0]["ok"]

    inbox = client.get("/api/notifications").json()
    assert inbox["unread"] == 2
    assert [(n["kind"], n["old_price"], n["new_price"]) for n in inbox["notes"]] == [
        ("lowest", 300, 240),
        ("target", 300, 240),
    ]
    note = inbox["notes"][0]
    assert note["product_id"] == product_id and note["product_name"] == "Serum"
    assert note["store_name"] == "Gratis" and note["read"] is False
    assert [title for title, _ in desktop.sent] == ["At your alert price", "Lowest price ever"]
    assert "₺240,00" in desktop.sent[0][1]

    assert client.post(f"/api/notifications/{note['id']}/read").status_code == 204
    assert client.get("/api/notifications").json()["unread"] == 1
    assert client.post("/api/notifications/read").status_code == 204
    inbox = client.get("/api/notifications").json()
    assert inbox["unread"] == 0 and all(n["read"] for n in inbox["notes"])
    assert client.post("/api/notifications/999/read").status_code == 404


def test_checking_one_product_notes_too(client, fake_pages, desktop):
    product_id = client.post("/api/products", json={"url": URL, "name": "Serum"}).json()["id"]
    for price in (300, 280):
        fake_pages[URL] = page(price)
        client.post(f"/api/products/{product_id}/check")
    assert [n["kind"] for n in client.get("/api/notifications").json()["notes"]] == ["lowest"]


def test_a_failing_desktop_notification_doesnt_break_the_check(client, fake_pages, desktop):
    desktop.fail = True
    product_id = client.post("/api/products", json={"url": URL, "name": "Serum"}).json()["id"]
    for price in (300, 280):
        fake_pages[URL] = page(price)
        result = client.post(f"/api/products/{product_id}/check").json()
    assert result["ok"] and result["price"] == 280
    assert client.get("/api/notifications").json()["unread"] == 1


def test_desktop_notifications_can_be_turned_off(settings, fake_pages, desktop):
    from fastapi.testclient import TestClient

    from price_diaries.api import create_app

    settings.desktop_notifications = False
    with TestClient(create_app(settings)) as client:
        product_id = client.post("/api/products", json={"url": URL, "name": "Serum"}).json()["id"]
        for price in (300, 280):
            fake_pages[URL] = page(price)
            client.post(f"/api/products/{product_id}/check")
        assert client.get("/api/notifications").json()["unread"] == 1
    assert desktop.sent == []


def test_the_daily_check_notes_and_notifies(client, fake_pages, desktop, monkeypatch):
    import asyncio

    from price_diaries import scheduler
    from tests.conftest import FakeFetcher

    monkeypatch.setattr(scheduler, "Fetcher", FakeFetcher)
    client.post("/api/products", json={"url": URL, "name": "Serum"})
    for price in (300, 280):
        fake_pages[URL] = page(price)
        asyncio.run(scheduler.run_daily_check(client.app.state.db, client.app.state.settings))
    assert [title for title, _ in desktop.sent] == ["Lowest price ever"]


# --- the demo ----------------------------------------------------------------------------------


def test_demo_fills_the_inbox_without_desktop_notifications(client, desktop):
    with client.app.state.db.session() as session:
        seed_demo(session)
    inbox = client.get("/api/notifications").json()
    # Plus, in the Sunday paper's week, a cheaper find (read) and the paper itself (new).
    assert len(inbox["notes"]) == len(DEMO_NOTES) + 2
    assert inbox["unread"] == sum(not read for *_, read in DEMO_NOTES) + 1
    assert {n["kind"] for n in inbox["notes"]} == {
        "target",
        "lowest",
        "fake_sale",
        "cheaper",
        "back_in_stock",
        "sunday_paper",
    }
    cheaper = next(n for n in inbox["notes"] if n["kind"] == "cheaper")
    assert cheaper["other_store_name"] == "Watsons" and cheaper["new_price"] < cheaper["old_price"]
    target = next(n for n in inbox["notes"] if n["kind"] == "target")
    product = client.get(f"/api/products/{target['product_id']}").json()
    assert product["summary"]["current"] <= product["target_price"]
    assert desktop.sent == []


# --- the desktop notifier itself (desktop-notifier mocked) --------------------------------------


class FakeToaster:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.sent: list[dict] = []

    async def send(self, **kwargs):
        if self.fail:
            raise OSError("toast service crashed")
        self.sent.append(kwargs)


async def test_unavailable_notifications_are_logged_once(monkeypatch, caplog):
    import desktop_notifier.main

    monkeypatch.setattr(desktop_notifier.main, "get_backend_class", lambda: DummyNotificationCenter)
    notifier = RealDesktop()
    with caplog.at_level(logging.WARNING):
        assert await notifier.send("Title", "Text") is False
        assert await notifier.send("Title", "Text") is False
    assert [r.message for r in caplog.records].count(
        "Desktop notifications aren't available (this system has no notification service). "
        "Notes still go to the inbox."
    ) == 1


async def test_sends_through_desktop_notifier_and_survives_failures(caplog):
    notifier = RealDesktop()
    notifier._notifier = FakeToaster()
    assert await notifier.send("Lowest price ever", "Toner at Gratis is now ₺10,00.")
    assert notifier._notifier.sent == [
        {"title": "Lowest price ever", "message": "Toner at Gratis is now ₺10,00."}
    ]
    notifier._notifier = FakeToaster(fail=True)
    with caplog.at_level(logging.WARNING):
        assert await notifier.send("Title", "Text") is False
    assert "toast service crashed" in caplog.text


# --- price-diaries notify test ------------------------------------------------------------------


def test_notify_test_sends_one_notification(monkeypatch, desktop, capsys):
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(desktop_notifications=True))
    assert cli.main(["notify", "test"]) == 0
    assert len(desktop.sent) == 1
    assert "Sent a test notification." in capsys.readouterr().out


def test_notify_test_says_when_notifications_are_off(monkeypatch, desktop, capsys):
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(desktop_notifications=False))
    assert cli.main(["notify", "test"]) == 1
    assert desktop.sent == []
    assert "PD_DESKTOP_NOTIFICATIONS=true" in capsys.readouterr().out


def test_notify_test_says_when_it_couldnt(monkeypatch, capsys):
    class Unavailable(FakeDesktop):
        async def send(self, title: str, message: str) -> bool:
            return False

    from price_diaries import notifications

    monkeypatch.setattr(notifications, "DesktopNotifications", Unavailable)
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(desktop_notifications=True))
    assert cli.main(["notify", "test"]) == 1
    assert "Couldn't show" in capsys.readouterr().out
