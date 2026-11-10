PAGE = (
    '<script type="application/ld+json">'
    '{"@type": "Product", "offers": {"price": "289.90", "priceCurrency": "TRY"}}'
    "</script>"
)
URL = "https://www.gratis.com/serum-p-1"


def add_product(client, **overrides):
    body = {"url": URL, "name": "Serum", "category": "Serum", "target_price": 300} | overrides
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
