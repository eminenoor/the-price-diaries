import pytest

from price_diaries import cli, fetcher
from tests.conftest import FakeFetcher
from tests.test_parsers import GRATIS_MEMBER_PAGE, JSON_LD_PAGE

URL = "https://www.gratis.com/tonikler/demo-tonik-p-1"
HINT = "Try again with --browser"


@pytest.fixture
def fake_pages(monkeypatch):
    monkeypatch.setattr(fetcher, "Fetcher", FakeFetcher)
    monkeypatch.setattr(FakeFetcher, "pages", {})
    return FakeFetcher.pages


def test_inspect_no_browser_hint_when_member_price_found(fake_pages, capsys):
    fake_pages[URL] = GRATIS_MEMBER_PAGE
    assert cli.main(["inspect", URL]) == 0
    out = capsys.readouterr().out
    assert "490.0" in out
    assert HINT not in out


def test_inspect_suggests_browser_when_member_price_missing(fake_pages, capsys):
    fake_pages[URL] = JSON_LD_PAGE
    assert cli.main(["inspect", URL]) == 0
    assert HINT in capsys.readouterr().out
