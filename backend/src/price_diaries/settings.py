"""App configuration, read from environment variables or a .env file."""

from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PD_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/prices.db"
    # Where `price-diaries demo` writes, and what `serve --demo` opens. Never your real prices.
    demo_database_url: str = "sqlite:///./data/demo.db"
    # Daily automatic check, in local time.
    check_hour: int = 9
    check_minute: int = 17
    scheduler_enabled: bool = True
    # Politeness: random pause between requests to the same store (seconds).
    min_delay: float = 3.0
    max_delay: float = 7.0
    request_timeout: float = 20.0
    # Use a headless browser when a page has no price in its HTML.
    browser_fallback: bool = True
    # You have the store's loyalty card (e.g. Gratis Gold/Platinum): track that price.
    use_member_prices: bool = True
    # Windows (or macOS/Linux) notifications for new notes while the app runs.
    desktop_notifications: bool = True
    # Built frontend (npm run build). Served at / when it exists.
    frontend_dir: str | None = "../frontend/dist"
    # Show the app as it looks on this day: which prices count as "checked today" and which
    # Sunday paper is the latest. For the demo data (PD_TODAY=2026-12-01); leave it unset
    # for daily use. Checks still record the real time.
    today: date | None = None

    def current_date(self) -> date:
        return self.today or date.today()


@lru_cache
def get_settings() -> Settings:
    return Settings()
