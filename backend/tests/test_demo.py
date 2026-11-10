from price_diaries.demo import DEMO_PRODUCTS, EMPTY_FLOOR, seed_demo


def test_demo_covers_every_state_and_floor(client):
    with client.app.state.db.session() as session:
        assert seed_demo(session) == len(DEMO_PRODUCTS)

    products = {p["name"]: p for p in client.get("/api/products").json()}
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
