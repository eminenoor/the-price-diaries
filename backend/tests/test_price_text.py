import pytest

from price_diaries.parsers import detect_currency, parse_price


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.299,90 TL", 1299.90),
        ("₺289,99", 289.99),
        ("289.99", 289.99),
        ("1,299.90 $", 1299.90),
        ("1.299 TL", 1299.0),
        ("1,299", 1299.0),
        ("  349 ₺ ", 349.0),
        ("12.499,00", 12499.0),
        (159, 159.0),
        ("Fiyat yok", None),
        (None, None),
    ],
)
def test_parse_price(text, expected):
    assert parse_price(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [("289,99 TL", "TRY"), ("₺10", "TRY"), ("€5", "EUR"), ("$5", "USD"), ("5", "TRY")],
)
def test_detect_currency(text, expected):
    assert detect_currency(text) == expected
