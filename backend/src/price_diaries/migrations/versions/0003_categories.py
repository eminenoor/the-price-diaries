"""Categories as floors (top level) and rooms (children); products point at a room.

Seeds the four floors. Existing free-text categories become rooms on the
Skincare floor, since every store tracked so far is a beauty store.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FLOORS = [
    ("Skincare", "#E8B4B8"),
    ("Pantry", "#C9D6A3"),
    ("Cleaning", "#A8C8E0"),
    ("Supplements", "#E6C9A8"),
]


def upgrade() -> None:
    categories = op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("color", sa.String(7), nullable=False),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])
    op.bulk_insert(categories, [{"name": n, "color": c, "parent_id": None} for n, c in FLOORS])

    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("category_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_products_category_id", "categories", ["category_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_products_category_id", ["category_id"])

    conn = op.get_bind()
    skincare_id, skincare_color = conn.execute(
        sa.text("SELECT id, color FROM categories WHERE name = 'Skincare' AND parent_id IS NULL")
    ).one()
    names = conn.execute(
        sa.text("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
    ).scalars()
    for name in [n for n in names if n.strip()]:
        room_id = conn.execute(
            sa.text(
                "INSERT INTO categories (name, parent_id, color) VALUES (:n, :p, :c) RETURNING id"
            ),
            {"n": name.strip()[:50], "p": skincare_id, "c": skincare_color},
        ).scalar_one()
        conn.execute(
            sa.text("UPDATE products SET category_id = :r WHERE category = :n"),
            {"r": room_id, "n": name},
        )

    with op.batch_alter_table("products") as batch:
        batch.drop_column("category")


def downgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("category", sa.String(50), nullable=True))
    op.execute(
        "UPDATE products SET category = "
        "(SELECT name FROM categories WHERE categories.id = products.category_id)"
    )
    with op.batch_alter_table("products") as batch:
        batch.drop_index("ix_products_category_id")
        batch.drop_constraint("fk_products_category_id", type_="foreignkey")
        batch.drop_column("category_id")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_table("categories")
