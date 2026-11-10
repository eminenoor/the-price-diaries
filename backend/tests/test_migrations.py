from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from price_diaries import migrate
from price_diaries.db import Base


def test_migrations_match_models(tmp_path):
    """Fails if a model changed without a matching Alembic migration."""
    url = f"sqlite:///{tmp_path / 'm.db'}"
    migrate.upgrade(url)
    with create_engine(url).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
