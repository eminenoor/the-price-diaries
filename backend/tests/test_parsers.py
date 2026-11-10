import pytest

from price_diaries.parsers import Parser, PriceNotFoundError, store_for_host

JSON_LD_PAGE = """
<html><head>
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [
  {"@type": "BreadcrumbList"},
  {"@type": "Product", "name": "Serum",
   "offers": {"@type": "Offer", "price": "289.99", "priceCurrency": "TRY",
              "availability": "https://schema.org/InStock"}}
]}
</script></head><body></body></html>
"""

META_PAGE = """
<html><head>
<meta property="product:price:amount" content="1299.90">
<meta property="product:price:currency" content="TRY">
</head></html>
"""

OUT_OF_STOCK_PAGE = """
<script type="application/ld+json">
{"@type": "Product", "offers": [{"price": 99, "priceCurrency": "TRY",
  "availability": "https://schema.org/OutOfStock"}]}
</script>
"""


def test_json_ld_is_preferred():
    result = Parser().parse(JSON_LD_PAGE)
    assert (result.price, result.currency, result.source) == (289.99, "TRY", "json-ld")


def test_meta_tags():
    result = Parser().parse(META_PAGE)
    assert (result.price, result.source) == (1299.90, "meta")


def test_custom_selector_wins():
    html = '<span class="old">500 TL</span><span id="now">399,90 TL</span>'
    result = Parser().parse(html, selector="#now")
    assert (result.price, result.source) == (399.90, "custom-selector")


def test_out_of_stock_detected():
    assert Parser().parse(OUT_OF_STOCK_PAGE).in_stock is False


def test_missing_price_raises():
    with pytest.raises(PriceNotFoundError):
        Parser().parse("<html><body>Hello</body></html>")


@pytest.mark.parametrize(
    ("host", "html", "expected"),
    [
        (
            "www.trendyol.com",
            '<div class="product-price-container"><span class="prc-dsc">249,99 TL</span></div>',
            249.99,
        ),
        (
            "www.trendyol.com",
            '<div class="price-wrapper-container"><span>Son 14 Günün En Düşük Fiyatı!</span>'
            '<div class="price-view"><span class="original">375 TL</span>'
            '<span class="discounted">349 TL</span></div></div>',
            349.0,
        ),
        (
            "www.amazon.com.tr",
            '<div id="corePriceDisplay_desktop_feature_div"><span class="a-price">'
            '<span class="a-offscreen">1.149,00 TL</span></span></div>',
            1149.0,
        ),
        ("www.gratis.com", '<span class="discounted-price">₺89,90</span>', 89.90),
    ],
)
def test_store_selectors(host, html, expected):
    store = store_for_host(host)
    assert store is not None
    assert store.parser().parse(html).price == expected


@pytest.mark.parametrize(
    ("host", "key"),
    [
        ("gratis.com", "gratis"),
        ("www.trendyol.com", "trendyol"),
        ("www.amazon.com.tr", "amazon"),
        ("www.watsons.com.tr", "watsons"),
        ("www.rossmann.com.tr", "rossmann"),
        ("www.eveshop.com.tr", "eveshop"),
        ("www.sephora.com.tr", "sephora"),
    ],
)
def test_store_lookup(host, key):
    assert store_for_host(host).key == key


def test_unknown_store():
    assert store_for_host("evil.example") is None


GRATIS_MEMBER_PAGE = """
<script type="application/ld+json">
{"@type": "Product", "offers": {"price": "950.00", "priceCurrency": "TRY"}}
</script>
<span class="badge">Gratis'e Özel</span>
<div class="card-box">
  <div class="title">Gold&amp;Platinum Özel Fiyat</div>
  <div class="amount"><span>490,00</span> TL</div>
</div>
<div class="price">950,00 TL</div>
"""


def test_gratis_member_price():
    result = store_for_host("www.gratis.com").parser().parse(GRATIS_MEMBER_PAGE)
    assert (result.price, result.member_price) == (950.0, 490.0)


def test_member_price_must_be_cheaper():
    html = GRATIS_MEMBER_PAGE.replace("490,00", "990,00")
    assert store_for_host("www.gratis.com").parser().parse(html).member_price is None


def test_no_member_label_no_member_price():
    assert store_for_host("www.gratis.com").parser().parse(JSON_LD_PAGE).member_price is None


def test_explain_lists_every_strategy():
    found = store_for_host("www.gratis.com").parser().explain(GRATIS_MEMBER_PAGE)
    assert found["json-ld"] == 950.0
    assert found["member price"] == 490.0
    assert found["meta tags"] is None


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (
            '<meta property="og:image" content="https://cdn.example/toner.jpg">' + JSON_LD_PAGE,
            "https://cdn.example/toner.jpg",
        ),
        (
            '<script type="application/ld+json">{"@type": "Product", "image": '
            '["https://cdn.example/a.jpg"], "offers": {"price": 10}}</script>',
            "https://cdn.example/a.jpg",
        ),
        (
            '<script type="application/ld+json">{"@type": "Product", "image": '
            '{"@type": "ImageObject", "url": "https://cdn.example/b.jpg"}, '
            '"offers": {"price": 10}}</script>',
            "https://cdn.example/b.jpg",
        ),
        # Not https, or relative: ignored.
        ('<meta property="og:image" content="http://cdn.example/a.jpg">' + JSON_LD_PAGE, None),
        ('<meta property="og:image" content="/img/a.jpg">' + JSON_LD_PAGE, None),
        ('<meta property="og:image" content="javascript:alert(1)">' + JSON_LD_PAGE, None),
        (JSON_LD_PAGE, None),
    ],
)
def test_product_image(html, expected):
    assert Parser().parse(html).image_url == expected
