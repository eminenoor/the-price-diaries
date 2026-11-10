from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from price_diaries import api
from price_diaries.api import create_app
from price_diaries.fetcher import FetchError
from price_diaries.settings import Settings


class FakeFetcher:
    """Stands in for the network. Maps URL -> HTML; unknown URLs fail like a 404."""

    pages: dict[str, str] = {}

    def __init__(self, *_, **__):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def get(self, url: str) -> str:
        if url not in self.pages:
            raise FetchError("Store answered 404.")
        return self.pages[url]

    async def get_rendered(self, url: str) -> str:
        return await self.get(url)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        scheduler_enabled=False,
        min_delay=0,
        max_delay=0,
        frontend_dir=None,
    )


@pytest.fixture
def fake_pages(monkeypatch) -> dict[str, str]:
    FakeFetcher.pages = {}
    monkeypatch.setattr(api, "Fetcher", FakeFetcher)
    return FakeFetcher.pages


@pytest.fixture
def client(settings, fake_pages) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
