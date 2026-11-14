from price_diaries.demo import DEMO_PRODUCTS, EMPTY_FLOOR, seed_demo


def test_demo_covers_every_state_and_floor(client):
    with client.app.state.db.session() as session:
        assert seed_demo(session) == len(DEMO_PRODUCTS)

    products = {p["listing_name"]: p for p in client.get("/api/products").json()}
    categories = {c["id"]: c for c in client.get("/api/categories").json()}

    floors = set()
    for demo in DEMO_PRODUCTS:
        product = products[demo.name]
        room = categories[product["category_id"]]
        floors.add(categories[room["parent_id"]]["name"])
        s = product["summary"]
        if demo.ending == "waiting":
            assert s is None
            continue
        assert s is not None, demo.name
        assert product["brand"] == demo.brand
        if demo.ending == "two_days":
            assert len(client.get(f"/api/products/{product['id']}").json()["history"]) == 2
            assert s["is_all_time_low"] and s["change_pct"] < 0, demo.name
            continue
        if demo.ending == "first":
            assert s["previous"] is None and s["change_pct"] is None, demo.name
            continue
        if demo.ending == "deal":
            assert s["is_all_time_low"] and s["change_pct"] < 0 and not s["fake_sale"], demo.name
        elif demo.ending == "fake":
            assert s["fake_sale"], demo.name
        elif demo.ending == "up":
            assert s["change_pct"] > 0 and not s["fake_sale"], demo.name
        else:
            assert s["change_pct"] == 0 and not s["fake_sale"], demo.name
        assert product["blocked"] is (demo.ending == "blocked")
        assert (product["regular_price"] is not None) is (demo.member_share is not None)

    assert floors == {"Skincare", "Pantry", "Cleaning", "Supplements"}
    empty = [c for c in categories.values() if c["name"] == EMPTY_FLOOR]
    assert len(empty) == 1 and empty[0]["parent_id"] is None
    assert not any(p["category_id"] == empty[0]["id"] for p in products.values())
    assert any(p["brand"] is None for p in products.values())


def test_demo_has_the_same_product_at_two_stores(client):
    with client.app.state.db.session() as session:
        seed_demo(session)
    products = {p["listing_name"]: p for p in client.get("/api/products").json()}

    toner = products["AHA BHA PHA 30 Days Miracle Toner 150 ml"]["cheaper_elsewhere"]
    assert toner["store_name"] == "Watsons" and toner["saving"] > 0
    # A bigger bottle compared per ml: 1,5 L for ₺165 is ₺275 for 2,5 L.
    laundry = products["Laundry Liquid 2.5 l"]["cheaper_elsewhere"]
    assert laundry["store_name"] == "Trendyol" and laundry["saving"] == 14


def test_new_demo_products_dont_change_the_old_ones(client):
    """Products share one random stream, so new ones go at the end of the list. Inserting one
    in the middle once turned the Niacinamide toner from "lowest ever" into "no change"."""
    with client.app.state.db.session() as session:
        seed_demo(session)
    products = {p["listing_name"]: p for p in client.get("/api/products").json()}
    toner = products["Niacinamide 10% Toner 200 ml"]["summary"]
    assert toner["is_all_time_low"] and toner["highest"] == 272.08
