"""App configuration, read from environment variables or a .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PD_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/prices.db"
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
    # Built frontend (npm run build). Served at / when it exists.
    frontend_dir: str | None = "../frontend/dist"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
