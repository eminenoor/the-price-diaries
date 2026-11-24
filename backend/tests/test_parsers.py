import pytest

from price_diaries.parsers import Parser, PriceNotFoundError, Size, store_for_host

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


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (
            '<script type="application/ld+json">{"@type": "Product", "brand": '
            '{"@type": "Brand", "name": "Some By Mi"}, "offers": {"price": 10}}</script>',
            "Some By Mi",
        ),
        (
            '<script type="application/ld+json">{"@graph": [{"@type": "Product", '
            '"brand": "  COSRX ", "offers": {"price": 10}}]}</script>',
            "COSRX",
        ),
        (
            '<script type="application/ld+json">{"@type": "Product", "brand": '
            '[{"name": "La Roche-Posay"}], "offers": {"price": 10}}</script>',
            "La Roche-Posay",
        ),
        ('<meta property="product:brand" content="Bioderma">' + META_PAGE, "Bioderma"),
        (
            '<div itemprop="brand" itemscope><span itemprop="name">The Ordinary</span></div>'
            + META_PAGE,
            "The Ordinary",
        ),
        # JSON-LD wins over meta tags.
        (
            '<meta property="product:brand" content="Gratis">'
            '<script type="application/ld+json">{"@type": "Product", "brand": '
            '{"name": "Some By Mi"}, "offers": {"price": 10}}</script>',
            "Some By Mi",
        ),
        # Empty, or not a Product's brand: none.
        (
            '<script type="application/ld+json">{"@type": "Product", "brand": {"name": " "}, '
            '"offers": {"price": 10}}</script>',
            None,
        ),
        (
            '<script type="application/ld+json">{"@type": "Organization", "brand": "Gratis"}'
            "</script>" + META_PAGE,
            None,
        ),
        (JSON_LD_PAGE, None),
    ],
)
def test_product_brand(html, expected):
    assert Parser().parse(html).brand == expected


def test_overlong_brand_is_ignored():
    html = f'<meta property="product:brand" content="{"x" * 101}">' + META_PAGE
    assert Parser().parse(html).brand is None


def _product_ld(fields: str) -> str:
    return (
        '<script type="application/ld+json">{"@type": "Product", '
        + fields
        + ', "offers": {"price": "99.90", "priceCurrency": "TRY"}}</script>'
    )


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (_product_ld('"size": "150 ml"'), Size(150, "ml")),
        (_product_ld('"weight": {"value": 1.5, "unitCode": "KGM"}'), Size(1500, "g")),
        (_product_ld('"weight": {"value": "500", "unitText": "gr"}'), Size(500, "g")),
        (_product_ld('"name": "Tonik 200 ML"'), Size(200, "ml")),
        (_product_ld('"size": "Büyük", "name": "Şampuan 1,5 L"'), Size(1500, "ml")),
        (
            '<meta property="og:title" content="Bulaşık Tableti 60 Adet">' + META_PAGE,
            Size(60, "pcs"),
        ),
        (JSON_LD_PAGE, None),
    ],
)
def test_product_size(html, expected):
    assert Parser().parse(html).size == expected


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (_product_ld('"gtin13": "8809598452350"'), "08809598452350"),
        (_product_ld('"gtin": 36000291452'), None),  # a number that lost its leading 0
        (_product_ld('"gtin": "036000291452"'), "00036000291452"),
        (_product_ld('"gtin13": "8809598452351", "gtin": "036000291452"'), "00036000291452"),
        (
            '<script type="application/ld+json">{"@type": "Product", "offers": '
            '{"@type": "Offer", "price": "99.90", "gtin13": "8809598452350"}}</script>',
            "08809598452350",
        ),
        ('<meta itemprop="gtin13" content="8809598452350">' + META_PAGE, "08809598452350"),
        ('<meta property="product:ean" content="8809598452350">' + META_PAGE, "08809598452350"),
        ('<span itemprop="gtin13">8809598452350</span>' + META_PAGE, "08809598452350"),
        (_product_ld('"sku": "8809598452350"'), None),  # a SKU isn't a barcode
        (JSON_LD_PAGE, None),
    ],
)
def test_product_barcode(html, expected):
    assert Parser().parse(html).gtin == expected
