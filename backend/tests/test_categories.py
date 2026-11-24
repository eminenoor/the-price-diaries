URL = "https://www.gratis.com/tonik-p-1"


def floor_id(client, name="Skincare") -> int:
    floors = [c for c in client.get("/api/categories").json() if c["parent_id"] is None]
    return next(c["id"] for c in floors if c["name"] == name)


def add_room(client, name="Toners", floor="Skincare", **extra):
    body = {"name": name, "parent_id": floor_id(client, floor)} | extra
    return client.post("/api/categories", json=body)


def test_lists_seeded_floors(client):
    names = [c["name"] for c in client.get("/api/categories").json()]
    assert names == ["Skincare", "Pantry", "Cleaning", "Supplements"]


def test_rooms_follow_their_floor_and_inherit_its_colour(client):
    skincare = floor_id(client)
    add_room(client, "Toners")
    add_room(client, "Moisturizers")
    add_room(client, "Coffee", floor="Pantry")
    listed = client.get("/api/categories").json()
    assert [c["name"] for c in listed] == [
        "Skincare", "Moisturizers", "Toners", "Pantry", "Coffee", "Cleaning", "Supplements",
    ]  # fmt: skip
    toners = next(c for c in listed if c["name"] == "Toners")
    assert toners["parent_id"] == skincare
    assert toners["color"] == next(c["color"] for c in listed if c["id"] == skincare)


def test_add_floor_with_colour(client):
    created = client.post("/api/categories", json={"name": "Pets", "color": "#a1b2c3"})
    assert created.status_code == 201
    assert created.json() | {"id": 0} == {
        "id": 0,
        "name": "Pets",
        "parent_id": None,
        "color": "#A1B2C3",
    }


def test_rooms_only_inside_floors(client):
    room = add_room(client).json()
    nested = client.post("/api/categories", json={"name": "AHA", "parent_id": room["id"]})
    assert nested.status_code == 422
    missing = client.post("/api/categories", json={"name": "AHA", "parent_id": 999})
    assert missing.status_code == 422


def test_duplicate_names_are_rejected_per_level(client):
    add_room(client, "Toners")
    assert add_room(client, "toners").status_code == 409
    assert add_room(client, "Toners", floor="Pantry").status_code == 201
    floor = client.post("/api/categories", json={"name": "skincare"})
    assert floor.status_code == 409


def test_bad_colour_is_rejected(client):
    assert add_room(client, color="red").status_code == 422


def test_product_in_a_room(client):
    room = add_room(client).json()
    product = client.post(
        "/api/products", json={"url": URL, "name": "Toner", "category_id": room["id"]}
    )
    assert product.status_code == 201
    assert product.json()["category_id"] == room["id"]


def test_product_with_unknown_category_is_rejected(client):
    body = {"url": URL, "name": "Toner", "category_id": 999}
    assert client.post("/api/products", json=body).status_code == 422
