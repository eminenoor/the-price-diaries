from datetime import date, timedelta

from price_diaries import demo
from price_diaries.demo import (
    DEMO_PRODUCTS,
    DEMO_TODAY,
    EFSANE_CUMA,
    EMPTY_FLOOR,
    demo_checks,
    seed_demo,
)

FLOORS = {"Skincare", "Haircare", "Pantry", "Cleaning", "Supplements"}


def by_name(client) -> dict[str, dict]:
    return {p["listing_name"]: p for p in client.get("/api/products").json()}


def test_demo_covers_every_state_and_floor(demo_client):
    products = by_name(demo_client)
    categories = {c["id"]: c for c in demo_client.get("/api/categories").json()}

    floors: dict[str, int] = {}
    for item in DEMO_PRODUCTS:
        product = products[item.name]
        room = categories[product["category_id"]]
        floor = categories[room["parent_id"]]["name"]
        floors[floor] = floors.get(floor, 0) + 1
        s = product["summary"]
        if item.ending == "waiting":
            assert s is None
            continue
        assert s is not None, item.name
        assert product["brand"] == item.brand
        assert product["blocked"] is (item.ending == "blocked"), item.name
        assert (product["last_error"] is not None) is (item.ending in ("blocked", "error"))
        if item.ending == "two_days":
            history = demo_client.get(f"/api/products/{product['id']}").json()["history"]
            assert len(history) == 2
            assert s["is_all_time_low"] and s["change_pct"] < 0, item.name
            continue
        if item.ending == "first":
            assert s["previous"] is None and s["change_pct"] is None, item.name
            continue
        if item.ending == "deal":
            assert s["is_all_time_low"] and s["change_pct"] < 0 and not s["fake_sale"], item.name
        elif item.ending in ("fake", "spike"):
            assert s["fake_sale"], item.name
        elif item.ending == "up":
            assert s["change_pct"] > 0 and not s["fake_sale"], item.name
        elif item.ending == "steady":
            assert s["change_pct"] == 0 and not s["fake_sale"], item.name
        assert (product["regular_price"] is not None) is (item.member_share is not None)

    assert len(DEMO_PRODUCTS) == 36
    assert set(floors) == FLOORS and min(floors.values()) >= 5
    empty = [c for c in categories.values() if c["name"] == EMPTY_FLOOR]
    assert len(empty) == 1 and empty[0]["parent_id"] is None
    assert not any(p["category_id"] == empty[0]["id"] for p in products.values())
    assert any(p["brand"] is None for p in products.values())


def test_demo_has_half_a_year_of_history(demo_client):
    products = by_name(demo_client)

    def first_check(name: str) -> date:
        history = demo_client.get(f"/api/products/{products[name]['id']}").json()["history"]
        return date.fromisoformat(history[0]["checked_at"][:10])

    assert first_check("Niacinamide 10% Toner 200 ml") == DEMO_TODAY - timedelta(days=179)
    # Some were added later.
    assert first_check("Retinol 0.3% Night Cream 50 ml") == DEMO_TODAY - timedelta(days=119)


def test_demo_has_the_same_product_at_three_stores_and_in_two_sizes(demo_client):
    products = by_name(demo_client)
    toner = products["AHA BHA PHA 30 Days Miracle Toner 150 ml"]
    detail = demo_client.get(f"/api/products/{toner['id']}").json()
    assert {o["store_name"] for o in detail["elsewhere"]} == {"Watsons", "Trendyol"}
    # Its new low at Gratis (with the card) is the cheapest today.
    for name in (
        "Some By Mi AHA BHA PHA Miracle Toner 150 ml",
        "Some By Mi AHA-BHA-PHA 30 Days Miracle Toner 150ml",
    ):
        assert products[name]["cheaper_elsewhere"]["store_name"] == "Gratis"

    # The 1,5 L bottle on Efsane sale is cheaper per litre: ₺175,92 is ₺293,20 for 2,5 L.
    laundry = products["Laundry Liquid 2.5 l"]["cheaper_elsewhere"]
    assert laundry["store_name"] == "Trendyol" and laundry["saving"] == 56.75


def checks_of(name: str, **kwargs) -> list:
    item = next(p for p in DEMO_PRODUCTS if p.name == name)
    return demo_checks(item, **kwargs)


def test_demo_prices_behave_like_turkish_prices():
    def on(checks: list, day: date):
        return next(c for c in checks if c.at.date() == day)

    every = {p.name: demo_checks(p) for p in DEMO_PRODUCTS}
    long = {name: checks for name, checks in every.items() if len(checks) >= 120}

    # Inflation: the regular price lately is higher than half a year ago.
    risen = [
        name
        for name, checks in long.items()
        if checks[0].price and checks[0].price < max(c.price or 0 for c in checks[-10:])
    ]
    assert len(risen) >= 0.8 * len(long)

    # Efsane Cuma: most products are cheaper on the day than the week before.
    before, friday = EFSANE_CUMA - timedelta(days=8), EFSANE_CUMA
    cheaper = [
        name
        for name, checks in long.items()
        if (b := on(checks, before)).price and (f := on(checks, friday)).price and f.price < b.price
    ]
    assert len(cheaper) >= 0.6 * len(long)

    # Stock gaps, failed checks and a card price that comes and goes.
    assert any(not c.in_stock for checks in every.values() for c in checks[:-21])
    assert sum(c.error is not None for checks in every.values() for c in checks[:-21]) >= 3
    retinol = every["Retinol 0.3% Night Cream 50 ml"]
    assert any(c.member_price is None for c in retinol if c.price)
    assert any(c.member_price is not None for c in retinol[:-21])


def test_the_demo_is_the_same_every_run():
    def rows(seed: int) -> list:
        return [
            (c.at, c.price, c.member_price, c.in_stock, str(c.error))
            for p in DEMO_PRODUCTS
            for c in demo_checks(p, seed=seed)
        ]

    assert rows(7) == rows(7)
    assert rows(7) != rows(8)


def test_new_demo_products_dont_change_the_old_ones(client, monkeypatch):
    """Each product has its own random stream, so the order of the list (or a product added
    to it) never changes another product's history."""
    monkeypatch.setattr(demo, "DEMO_PRODUCTS", DEMO_PRODUCTS[::-1])
    with client.app.state.db.session() as session:
        seed_demo(session)
    toner = by_name(client)["Niacinamide 10% Toner 200 ml"]
    history = client.get(f"/api/products/{toner['id']}").json()["history"]
    expected = [c.price for c in checks_of("Niacinamide 10% Toner 200 ml") if c.price]
    assert [h["price"] for h in history] == expected
