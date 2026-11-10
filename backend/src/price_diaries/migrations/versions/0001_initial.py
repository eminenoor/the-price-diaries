"""Initial schema: products and price points.

Revision ID: 0001
Revises:
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(2048), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("store", sa.String(32), nullable=False),
        sa.Column("category", sa.String(50)),
        sa.Column("selector", sa.String(300)),
        sa.Column("target_price", sa.Float()),
        sa.Column("last_error", sa.String(500)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_products_store", "products", ["store"])

    op.create_table(
        "price_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("in_stock", sa.Boolean(), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_price_points_product_time", "price_points", ["product_id", "checked_at"])


def downgrade() -> None:
    op.drop_index("ix_price_points_product_time", table_name="price_points")
    op.drop_table("price_points")
    op.drop_index("ix_products_store", table_name="products")
    op.drop_table("products")
