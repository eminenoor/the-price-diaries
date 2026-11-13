import pytest

from price_diaries.parsers import normalize_gtin


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("8809598452350", "08809598452350"),  # EAN-13
        ("036000291452", "00036000291452"),  # UPC-12
        ("0036000291452", "00036000291452"),  # the same UPC written as EAN-13
        ("96385074", "00000096385074"),  # GTIN-8
        ("10036000291459", "10036000291459"),  # GTIN-14
        ("880 9598 452350", "08809598452350"),  # spaces
        ("880-9598-452350", "08809598452350"),  # dashes
        (8809598452350, "08809598452350"),  # a JSON number
    ],
)
def test_reads_barcode(value, expected):
    assert normalize_gtin(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        True,
        "8809598452351",  # wrong check digit
        "88095984523",  # 11 digits
        "880959845235012",  # 15 digits
        "ABC9598452350",
        "0000000000000",
        "SKU-12345",
    ],
)
def test_rejects_non_barcodes(value):
    assert normalize_gtin(value) is None
