import pytest

from price_diaries.security import UnsupportedURLError, validate_product_url


def test_valid_url_is_normalized():
    url, store = validate_product_url(
        "  https://WWW.Gratis.com/serum-p-123?utm_source=insta&color=red#reviews "
    )
    assert url == "https://www.gratis.com/serum-p-123?color=red"
    assert store.key == "gratis"


def test_trendyol_merchant_is_kept():
    url, _ = validate_product_url("https://www.trendyol.com/x/y-p-1?merchantId=42&utm_medium=a")
    assert url == "https://www.trendyol.com/x/y-p-1?merchantId=42"


@pytest.mark.parametrize(
    "url",
    [
        "http://www.gratis.com/serum",  # not https
        "https://localhost:8000/api/products",  # SSRF: own API
        "https://169.254.169.254/latest/meta-data",  # SSRF: cloud metadata
        "https://192.168.1.1/admin",  # SSRF: private network
        "https://user:pass@www.gratis.com/x",  # credentials
        "https://www.gratis.com:8443/x",  # odd port
        "https://gratis.com.evil.example/x",  # look-alike domain
        "file:///etc/passwd",
        "javascript:alert(1)",
    ],
)
def test_rejected_urls(url):
    with pytest.raises(UnsupportedURLError):
        validate_product_url(url)
