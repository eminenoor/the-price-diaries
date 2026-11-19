import logging
from datetime import date, timedelta

from fastapi.testclient import TestClient

from price_diaries.api import create_app
from price_diaries.fetcher import StoreBlockedError
from tests.conftest import FakeFetcher

PAGE = (
    '<script type="application/ld+json">'
    '{"@type": "Product", "offers": {"price": "289.90", "priceCurrency": "TRY"}}'
    "</script>"
)
URL = "https://www.gratis.com/serum-p-1"


def add_product(client, **overrides):
    body = {"url": URL, "name": "Serum", "target_price": 300} | overrides
    return client.post("/api/products", json=body)


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_lists_supported_stores(client):
    keys = {s["key"] for s in client.get("/api/stores").json()}
    assert {"gratis", "trendyol", "amazon", "sephora"} <= keys


def test_create_and_check_product(client, fake_pages):
    fake_pages[URL] = PAGE
    created = add_product(client)
    assert created.status_code == 201
    product_id = created.json()["id"]
    assert created.json()["store"] == "gratis"
    assert created.json()["summary"] is None

    result = client.post(f"/api/products/{product_id}/check").json()
    assert result == {"product_id": product_id, "ok": True, "price": 289.9, "error": None}

    detail = client.get(f"/api/products/{product_id}").json()
    assert detail["summary"]["current"] == 289.9
    assert len(detail["history"]) == 1
    assert detail["sparkline"] == [289.9]


def test_failed_check_records_error(client):
    product_id = add_product(client).json()["id"]
    result = client.post(f"/api/products/{product_id}/check").json()
    assert result["ok"] is False
    assert "404" in client.get(f"/api/products/{product_id}").json()["last_error"]


def test_check_all(client, fake_pages):
    fake_pages[URL] = PAGE
    add_product(client)
    add_product(client, url="https://www.watsons.com.tr/missing", name="Missing")
    results = client.post("/api/check").json()
    assert sorted(r["ok"] for r in results) == [False, True]


def test_rejects_unsupported_url(client):
    response = add_product(client, url="https://localhost/api/products")
    assert response.status_code == 422
    assert "not a supported store" in response.json()["detail"]


def test_rejects_duplicates(client):
    add_product(client)
    assert add_product(client, url=URL + "?utm_source=x").status_code == 409


def test_update_and_delete(client):
    product_id = add_product(client).json()["id"]
    updated = client.patch(f"/api/products/{product_id}", json={"target_price": 250})
    assert updated.json()["target_price"] == 250

    assert client.delete(f"/api/products/{product_id}").status_code == 204
    assert client.get(f"/api/products/{product_id}").status_code == 404


def test_serves_built_frontend(settings, fake_pages, tmp_path):
    from fastapi.testclient import TestClient

    from price_diaries.api import create_app

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div id=root></div>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("nope")
    settings.frontend_dir = str(dist)

    with TestClient(create_app(settings)) as client:
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert "root" in client.get("/products/3").text  # SPA route
        assert "nope" not in client.get("/..%2Fsecret.txt").text  # path traversal
        assert client.get("/api/health").json() == {"status": "ok"}


MEMBER_PAGE = PAGE + "<div><p>Gold&amp;Platinum Özel Fiyat</p><p>149,90 TL</p></div>"


def test_member_price_is_used(client, fake_pages):
    fake_pages[URL] = MEMBER_PAGE
    product_id = add_product(client).json()["id"]
    assert client.post(f"/api/products/{product_id}/check").json()["price"] == 149.9

    detail = client.get(f"/api/products/{product_id}").json()
    assert detail["summary"]["current"] == 149.9
    assert detail["regular_price"] == 289.9
    assert detail["history"][0]["member_price"] == 149.9


def test_member_price_found_after_javascript(client, fake_pages, monkeypatch):
    """Raw HTML has only the regular price; the rendered page adds the member price."""
    from tests.conftest import FakeFetcher

    async def rendered(self, url):
        return MEMBER_PAGE

    monkeypatch.setattr(FakeFetcher, "get_rendered", rendered)
    fake_pages[URL] = PAGE
    product_id = add_product(client).json()["id"]
    assert client.post(f"/api/products/{product_id}/check").json()["price"] == 149.9


def test_regular_price_when_member_prices_off(settings, fake_pages):
    from fastapi.testclient import TestClient

    from price_diaries.api import create_app

    settings.use_member_prices = False
    fake_pages[URL] = MEMBER_PAGE
    with TestClient(create_app(settings)) as client:
        product_id = add_product(client).json()["id"]
        client.post(f"/api/products/{product_id}/check")
        detail = client.get(f"/api/products/{product_id}").json()
    assert detail["summary"]["current"] == 289.9
    assert detail["regular_price"] is None


def test_check_stores_product_photo(client, fake_pages):
    fake_pages[URL] = '<meta property="og:image" content="https://cdn.example/serum.jpg">' + PAGE
    product_id = add_product(client).json()["id"]
    assert client.get(f"/api/products/{product_id}").json()["image_url"] is None
    client.post(f"/api/products/{product_id}/check")
    assert client.get(f"/api/products/{product_id}").json()["image_url"] == (
        "https://cdn.example/serum.jpg"
    )


def test_blocked_store_is_flagged(client, monkeypatch):
    async def refuse(self, url):
        raise StoreBlockedError("www.gratis.com", 403)

    monkeypatch.setattr(FakeFetcher, "get", refuse)
    product_id = add_product(client).json()["id"]
    result = client.post(f"/api/products/{product_id}/check").json()
    assert result["ok"] is False
    product = client.get(f"/api/products/{product_id}").json()
    assert product["blocked"] is True
    assert "blocks automated price checks" in product["last_error"]


def test_rate_limit_is_not_a_block(client, monkeypatch):
    async def slow_down(self, url):
        raise StoreBlockedError("www.gratis.com", 429)

    monkeypatch.setattr(FakeFetcher, "get", slow_down)
    product_id = add_product(client).json()["id"]
    client.post(f"/api/products/{product_id}/check")
    assert client.get(f"/api/products/{product_id}").json()["blocked"] is False


def test_successful_check_clears_block(client, fake_pages):
    fake_pages[URL] = PAGE
    product_id = add_product(client).json()["id"]
    client.post(f"/api/products/{product_id}/check")
    assert client.get(f"/api/products/{product_id}").json()["blocked"] is False


BRAND_PAGE = (
    '<script type="application/ld+json">'
    '{"@type": "Product", "brand": {"@type": "Brand", "name": "Some By Mi"}, '
    '"offers": {"price": "289.90", "priceCurrency": "TRY"}}'
    "</script>"
)


def test_check_stores_brand(client, fake_pages):
    fake_pages[URL] = BRAND_PAGE
    product_id = add_product(client).json()["id"]
    assert client.get(f"/api/products/{product_id}").json()["brand"] is None
    client.post(f"/api/products/{product_id}/check")
    assert client.get(f"/api/products/{product_id}").json()["brand"] == "Some By Mi"


def test_check_all_stores_brand(client, fake_pages):
    fake_pages[URL] = BRAND_PAGE
    add_product(client)
    client.post("/api/check")
    assert client.get("/api/products").json()[0]["brand"] == "Some By Mi"


def test_user_brand_survives_checks(client, fake_pages):
    fake_pages[URL] = BRAND_PAGE
    product_id = add_product(client).json()["id"]
    updated = client.patch(f"/api/products/{product_id}", json={"brand": "  Some  By Mi Lab "})
    assert updated.json()["brand"] == "Some By Mi Lab"
    client.post(f"/api/products/{product_id}/check")
    assert client.get(f"/api/products/{product_id}").json()["brand"] == "Some By Mi Lab"


def test_removed_brand_stays_removed(client, fake_pages):
    fake_pages[URL] = BRAND_PAGE
    product_id = add_product(client).json()["id"]
    client.post(f"/api/products/{product_id}/check")
    assert client.patch(f"/api/products/{product_id}", json={"brand": ""}).json()["brand"] is None
    client.post(f"/api/products/{product_id}/check")
    assert client.get(f"/api/products/{product_id}").json()["brand"] is None


def test_brand_length_is_limited(client):
    product_id = add_product(client).json()["id"]
    response = client.patch(f"/api/products/{product_id}", json={"brand": "x" * 101})
    assert response.status_code == 422


SIZE_PAGE = (
    '<script type="application/ld+json">'
    '{"@type": "Product", "size": "200 ml", "offers": {"price": "289.90", "priceCurrency": "TRY"}}'
    "</script>"
)


def test_size_from_name_on_create(client):
    product = add_product(client, name="Tonik 150 ml").json()
    assert product["size"] == {"amount": 150, "unit": "ml", "source": "name"}
    assert product["unit_price"] is None  # no price yet


def test_unit_price_uses_current_price(client, fake_pages):
    fake_pages[URL] = PAGE
    product_id = add_product(client, name="Serum 30 ml").json()["id"]
    client.post(f"/api/products/{product_id}/check")
    # ₺289,90 for 30 ml -> ₺96,63 per 10 ml
    product = client.get(f"/api/products/{product_id}").json()
    assert product["unit_price"] == {"price": 96.63, "per": 10, "unit": "ml"}


def test_unit_price_uses_member_price(client, fake_pages):
    fake_pages[URL] = MEMBER_PAGE
    product_id = add_product(client, name="Serum 30 ml").json()["id"]
    client.post(f"/api/products/{product_id}/check")
    # ₺149,90 card price for 30 ml -> ₺49,97 per 10 ml
    assert client.get("/api/products").json()[0]["unit_price"]["price"] == 49.97


def test_size_from_page_when_name_has_none(client, fake_pages):
    fake_pages[URL] = SIZE_PAGE
    product_id = add_product(client).json()["id"]
    assert client.get(f"/api/products/{product_id}").json()["size"] is None
    client.post("/api/check")
    product = client.get(f"/api/products/{product_id}").json()
    assert product["size"] == {"amount": 200, "unit": "ml", "source": "page"}
    assert product["unit_price"] == {"price": 14.5, "per": 10, "unit": "ml"}


def test_name_size_wins_over_page(client, fake_pages):
    fake_pages[URL] = SIZE_PAGE
    product_id = add_product(client, name="Serum 30 ml").json()["id"]
    client.post(f"/api/products/{product_id}/check")
    assert client.get(f"/api/products/{product_id}").json()["size"]["amount"] == 30


def test_user_size_survives_checks(client, fake_pages):
    fake_pages[URL] = SIZE_PAGE
    product_id = add_product(client, name="Serum 30 ml").json()["id"]
    updated = client.patch(f"/api/products/{product_id}", json={"size": "1,5 L"})
    assert updated.json()["size"] == {"amount": 1500, "unit": "ml", "source": "user"}
    client.post(f"/api/products/{product_id}/check")
    assert client.get(f"/api/products/{product_id}").json()["size"]["amount"] == 1500


def test_removed_size_stays_removed(client, fake_pages):
    fake_pages[URL] = SIZE_PAGE
    product_id = add_product(client, name="Serum 30 ml").json()["id"]
    removed = client.patch(f"/api/products/{product_id}", json={"size": ""}).json()
    assert removed["size"] is None
    client.post(f"/api/products/{product_id}/check")
    product = client.get(f"/api/products/{product_id}").json()
    assert product["size"] is None
    assert product["unit_price"] is None


def test_size_without_unit_is_rejected(client):
    product_id = add_product(client).json()["id"]
    response = client.patch(f"/api/products/{product_id}", json={"size": "150"})
    assert response.status_code == 422
    assert "150 ml" in response.json()["detail"]


def test_renaming_rereads_the_size(client):
    product_id = add_product(client, name="Serum 30 ml").json()["id"]
    renamed = client.patch(f"/api/products/{product_id}", json={"name": "Serum 50 ml"}).json()
    assert renamed["size"]["amount"] == 50
    renamed = client.patch(f"/api/products/{product_id}", json={"name": "Serum"}).json()
    assert renamed["size"] is None


WATSONS_URL = "https://www.watsons.com.tr/toner-p-2"


def barcode_page(price: str, gtin: str = "8809598452350") -> str:
    return (
        '<script type="application/ld+json">'
        f'{{"@type": "Product", "gtin13": "{gtin}", '
        f'"offers": {{"price": "{price}", "priceCurrency": "TRY"}}}}'
        "</script>"
    )


def two_stores(client, fake_pages, here="400.00", there="340.00", gtin="8809598452350"):
    """The same toner at Gratis and Watsons, both checked."""
    fake_pages[URL] = barcode_page(here)
    fake_pages[WATSONS_URL] = barcode_page(there, gtin)
    gratis = add_product(client, name="Toner 150 ml").json()["id"]
    watsons = add_product(client, url=WATSONS_URL, name="Toner 150 ml").json()["id"]
    client.post("/api/check")
    return gratis, watsons


def test_same_barcode_groups_products(client, fake_pages):
    gratis, watsons = two_stores(client, fake_pages)
    detail = client.get(f"/api/products/{gratis}").json()
    assert detail["gtin"] == "08809598452350"
    assert [o["product_id"] for o in detail["elsewhere"]] == [watsons]
    offer = detail["elsewhere"][0]
    assert offer["store_name"] == "Watsons"
    assert offer["price"] == 340
    assert offer["unit_price"] == {"price": 22.67, "per": 10, "unit": "ml"}
    assert offer["saving"] == 60


def test_home_notes_a_cheaper_store(client, fake_pages):
    gratis, watsons = two_stores(client, fake_pages)
    products = {p["id"]: p for p in client.get("/api/products").json()}
    assert products[gratis]["cheaper_elsewhere"] == {
        "product_id": watsons,
        "store": "watsons",
        "store_name": "Watsons",
        "saving": 60,
    }
    assert products[watsons]["cheaper_elsewhere"] is None  # it's the cheaper one


def test_the_app_says_when_pd_today_is_set(settings, caplog):
    with TestClient(create_app(settings)) as plain:
        assert plain.get("/api/app").json() == {"set_date": None}
    assert "PD_TODAY" not in caplog.text

    settings.today = date(2026, 12, 1)
    with caplog.at_level(logging.WARNING), TestClient(create_app(settings)) as demo:
        assert demo.get("/api/app").json() == {"set_date": "2026-12-01"}
    assert "PD_TODAY is set: the app treats 1 Dec 2026 as today, not the real date" in caplog.text


def test_pd_today_sets_the_day_the_app_shows(client, fake_pages):
    gratis, _ = two_stores(client, fake_pages)
    # On another day, today's checks aren't today's any more, so there's no cheaper store.
    client.app.state.settings.today = date.today() + timedelta(days=1)
    products = {p["id"]: p for p in client.get("/api/products").json()}
    assert products[gratis]["cheaper_elsewhere"] is None
    # And the latest paper is that day's: on Wednesday 18 November, the week of the 9th.
    client.app.state.settings.today = date(2026, 11, 18)
    assert client.get("/api/paper").json()["week_start"] == "2026-11-09"
    assert client.get("/api/paper?week=2026-11-16").status_code == 404


def test_cheaper_elsewhere_uses_member_price(client, fake_pages):
    two_stores(client, fake_pages, here="289.90", there="200.00")
    fake_pages[URL] = barcode_page("289.90") + MEMBER_PAGE.removeprefix(PAGE)
    client.post("/api/check")
    # The card price at Gratis (149,90) beats Watsons, so the note moves to Watsons' window.
    products = {p["store"]: p for p in client.get("/api/products").json()}
    assert products["gratis"]["cheaper_elsewhere"] is None
    assert products["watsons"]["cheaper_elsewhere"]["saving"] == 50.1


def test_different_barcodes_stay_apart(client, fake_pages):
    gratis, _ = two_stores(client, fake_pages, gtin="036000291452")
    assert client.get(f"/api/products/{gratis}").json()["elsewhere"] == []


def test_link_by_hand(client, fake_pages):
    gratis, watsons = two_stores(client, fake_pages, gtin="036000291452")
    linked = client.post(f"/api/products/{gratis}/link", json={"other_id": watsons}).json()
    assert [o["product_id"] for o in linked["elsewhere"]] == [watsons]
    # Both directions, and checks don't undo it although the barcodes differ.
    client.post("/api/check")
    other = client.get(f"/api/products/{watsons}").json()
    assert [o["product_id"] for o in other["elsewhere"]] == [gratis]


def test_link_joins_the_other_group(client, fake_pages):
    gratis, watsons = two_stores(client, fake_pages)
    fake_pages["https://www.watsons.com.tr/toner-p-3"] = PAGE
    third = add_product(client, url="https://www.watsons.com.tr/toner-p-3", name="Toner").json()
    client.post(f"/api/products/{third['id']}/link", json={"other_id": gratis})
    client.post(f"/api/products/{third['id']}/check")
    elsewhere = client.get(f"/api/products/{gratis}").json()["elsewhere"]
    assert {o["product_id"] for o in elsewhere} == {watsons, third["id"]}


def test_unlink_by_hand_survives_checks(client, fake_pages):
    gratis, watsons = two_stores(client, fake_pages)
    assert client.delete(f"/api/products/{watsons}/link").status_code == 204
    client.post("/api/check")
    assert client.get(f"/api/products/{gratis}").json()["elsewhere"] == []
    assert client.get(f"/api/products/{watsons}").json()["elsewhere"] == []


def test_cannot_link_to_itself_or_nothing(client):
    product_id = add_product(client).json()["id"]
    for other in (product_id, 999):
        response = client.post(f"/api/products/{product_id}/link", json={"other_id": other})
        assert response.status_code == 422


def test_unchecked_products_are_left_out_of_elsewhere(client, fake_pages):
    fake_pages[URL] = PAGE
    gratis = add_product(client).json()["id"]
    watsons = add_product(client, url=WATSONS_URL, name="Serum").json()["id"]
    client.post(f"/api/products/{gratis}/link", json={"other_id": watsons})
    assert client.get(f"/api/products/{gratis}").json()["elsewhere"] == []


def test_group_shares_the_most_complete_name(client, fake_pages):
    gratis, watsons = two_stores(client, fake_pages)
    client.patch(f"/api/products/{watsons}", json={"name": "Some By Mi Miracle Toner 150 ml"})
    products = {p["id"]: p for p in client.get("/api/products").json()}
    assert (
        products[gratis]["name"] == products[watsons]["name"] == "Some By Mi Miracle Toner 150 ml"
    )
    assert products[gratis]["listing_name"] == "Toner 150 ml"
    # The elsewhere list keeps each store's own name.
    elsewhere = client.get(f"/api/products/{gratis}").json()["elsewhere"]
    assert elsewhere[0]["name"] == "Some By Mi Miracle Toner 150 ml"
    assert client.get(f"/api/products/{watsons}").json()["elsewhere"][0]["name"] == "Toner 150 ml"


def test_renaming_a_group_renames_every_store(client, fake_pages):
    gratis, watsons = two_stores(client, fake_pages)
    renamed = client.patch(f"/api/products/{gratis}", json={"display_name": "  My  toner "})
    assert renamed.json()["name"] == "My toner"
    assert client.get(f"/api/products/{watsons}").json()["name"] == "My toner"
    # Store names, and the sizes read from them, are untouched.
    assert client.get(f"/api/products/{watsons}").json()["listing_name"] == "Toner 150 ml"
    assert client.get(f"/api/products/{watsons}").json()["size"]["amount"] == 150
    # "" goes back to the most complete store name.
    client.patch(f"/api/products/{watsons}", json={"display_name": ""})
    assert client.get(f"/api/products/{gratis}").json()["name"] == "Toner 150 ml"


def test_unlinked_product_gets_its_own_name_back(client, fake_pages):
    gratis, watsons = two_stores(client, fake_pages)
    client.patch(f"/api/products/{gratis}", json={"display_name": "My toner"})
    client.delete(f"/api/products/{watsons}/link")
    assert client.get(f"/api/products/{watsons}").json()["name"] == "Toner 150 ml"
    assert client.get(f"/api/products/{gratis}").json()["name"] == "My toner"


def test_linked_product_takes_the_group_name(client, fake_pages):
    gratis, watsons = two_stores(client, fake_pages, gtin="036000291452")
    client.patch(f"/api/products/{watsons}", json={"display_name": "Watsons only"})
    client.patch(f"/api/products/{gratis}", json={"display_name": "My toner"})
    client.post(f"/api/products/{watsons}/link", json={"other_id": gratis})
    assert client.get(f"/api/products/{watsons}").json()["name"] == "My toner"


def test_renaming_a_single_product(client):
    product_id = add_product(client, name="Serum 30 ml").json()["id"]
    renamed = client.patch(f"/api/products/{product_id}", json={"display_name": "Night serum"})
    assert renamed.json()["name"] == "Night serum"
    assert renamed.json()["listing_name"] == "Serum 30 ml"


def test_shared_name_keeps_each_stores_size(client, fake_pages):
    """A group can hold different pack sizes: the shared name never shows the wrong one."""
    gratis, watsons = two_stores(client, fake_pages, gtin="036000291452")
    client.patch(f"/api/products/{gratis}", json={"name": "Laundry Liquid 2.5 l"})
    client.patch(f"/api/products/{watsons}", json={"name": "Laundry Liquid 1.5 l"})
    client.post(f"/api/products/{watsons}/link", json={"other_id": gratis})
    products = {p["id"]: p["name"] for p in client.get("/api/products").json()}
    assert products == {gratis: "Laundry Liquid 2.5 l", watsons: "Laundry Liquid 1.5 l"}
    # A name the user picks gets each store's size too.
    client.patch(f"/api/products/{gratis}", json={"display_name": "My liquid 2,5 L"})
    assert client.get(f"/api/products/{watsons}").json()["name"] == "My liquid 1.5 l"
