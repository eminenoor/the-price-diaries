from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

from price_diaries import migrate
from price_diaries.db import Base


def test_migrations_match_models(tmp_path):
    """Fails if a model changed without a matching Alembic migration."""
    url = f"sqlite:///{tmp_path / 'm.db'}"
    migrate.upgrade(url)
    with create_engine(url).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_fresh_database_has_the_four_floors(tmp_path):
    url = f"sqlite:///{tmp_path / 'f.db'}"
    migrate.upgrade(url)
    with create_engine(url).connect() as conn:
        floors = conn.execute(
            text("SELECT name FROM categories WHERE parent_id IS NULL ORDER BY id")
        ).scalars()
        assert list(floors) == ["Skincare", "Pantry", "Cleaning", "Supplements"]


def test_category_text_becomes_rooms_on_skincare(tmp_path):
    url = f"sqlite:///{tmp_path / 'c.db'}"
    migrate.upgrade(url, "0002")
    engine = create_engine(url)
    with engine.begin() as conn:
        for i, category in enumerate(["Toner", "Toner", "Serum", None]):
            conn.execute(
                text(
                    "INSERT INTO products (url, name, store, category) "
                    "VALUES (:u, :n, 'gratis', :c)"
                ),
                {"u": f"https://www.gratis.com/p-{i}", "n": f"Product {i}", "c": category},
            )

    migrate.upgrade(url)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT p.name, room.name, floor.name FROM products p "
                "LEFT JOIN categories room ON room.id = p.category_id "
                "LEFT JOIN categories floor ON floor.id = room.parent_id ORDER BY p.id"
            )
        ).all()
    assert [tuple(r) for r in rows] == [
        ("Product 0", "Toner", "Skincare"),
        ("Product 1", "Toner", "Skincare"),
        ("Product 2", "Serum", "Skincare"),
        ("Product 3", None, None),
    ]

    config = Config()
    config.set_main_option("script_location", str(migrate.MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", url)
    command.downgrade(config, "0002")
    with engine.connect() as conn:
        names = conn.execute(text("SELECT category FROM products ORDER BY id")).scalars()
        assert list(names) == ["Toner", "Toner", "Serum", None]


def test_existing_products_get_a_size_from_their_name(tmp_path):
    url = f"sqlite:///{tmp_path / 's.db'}"
    migrate.upgrade(url, "0006")
    engine = create_engine(url)
    with engine.begin() as conn:
        for i, name in enumerate(["Tonik 150 ml", "Serum"]):
            conn.execute(
                text("INSERT INTO products (url, name, store) VALUES (:u, :n, 'gratis')"),
                {"u": f"https://www.gratis.com/p-{i}", "n": name},
            )

    migrate.upgrade(url)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT size_amount, size_unit, size_source FROM products ORDER BY id")
        ).all()
    assert [tuple(r) for r in rows] == [(150, "ml", "name"), (None, None, None)]
