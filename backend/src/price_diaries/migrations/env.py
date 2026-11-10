"""Alembic environment. Run via `price-diaries migrate` or `alembic upgrade head`."""

from alembic import context
from sqlalchemy import engine_from_config, pool

from price_diaries.db import Base
from price_diaries.settings import get_settings

config = context.config
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # lets SQLite handle ALTER TABLE
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
