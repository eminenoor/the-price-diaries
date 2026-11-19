import os

import pytest
import uvicorn
from sqlalchemy import func, select

from price_diaries import cli, fetcher, migrate
from price_diaries.db import Database, Product
from price_diaries.demo import DEMO_TODAY
from price_diaries.settings import get_settings
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


# --- the demo has its own database ------------------------------------------------------------


@pytest.fixture
def databases(tmp_path, monkeypatch):
    """A real database and a demo one, both in a temporary folder."""
    real, demo = f"sqlite:///{tmp_path / 'prices.db'}", f"sqlite:///{tmp_path / 'demo.db'}"
    # `serve --demo` sets variables itself: give it a copy of the environment to change.
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setenv("PD_DATABASE_URL", real)
    monkeypatch.setenv("PD_DEMO_DATABASE_URL", demo)
    monkeypatch.delenv("PD_TODAY", raising=False)
    get_settings.cache_clear()
    yield real, demo
    get_settings.cache_clear()


def products_in(url: str) -> int:
    with Database(url).session() as session:
        return session.scalar(select(func.count()).select_from(Product)) or 0


def test_demo_never_touches_the_real_database(databases, capsys):
    real, demo = databases
    migrate.upgrade(real)
    assert cli.main(["demo"]) == 0
    assert products_in(demo) == 36
    assert products_in(real) == 0
    assert "serve --demo" in capsys.readouterr().out
    # Again: it says so instead of adding the products twice.
    assert cli.main(["demo"]) == 1
    assert "already in" in capsys.readouterr().out
    assert products_in(demo) == 36


def test_demo_refuses_the_real_database(databases, monkeypatch, tmp_path, capsys):
    real, _ = databases
    # The same file, written another way, is still the real database.
    monkeypatch.setenv("PD_DEMO_DATABASE_URL", f"sqlite:///{tmp_path / '.' / 'prices.db'}")
    get_settings.cache_clear()
    migrate.upgrade(real)
    assert cli.main(["demo"]) == 1
    assert "real database" in capsys.readouterr().out
    assert products_in(real) == 0


def test_serve_demo_opens_the_demo_on_its_day(databases, monkeypatch):
    _, demo = databases
    served = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: served.append(get_settings()))
    assert cli.main(["serve", "--demo"]) == 0
    settings = served[0]
    assert settings.database_url == demo
    assert settings.today == DEMO_TODAY
    assert settings.scheduler_enabled is False
