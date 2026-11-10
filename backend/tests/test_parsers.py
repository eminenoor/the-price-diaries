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
