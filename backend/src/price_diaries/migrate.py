"""Run Alembic migrations from code (used by the CLI and on server start)."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from price_diaries.db import ensure_sqlite_dir

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def upgrade(database_url: str, revision: str = "head") -> None:
    ensure_sqlite_dir(database_url)
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, revision)
