"""Remember each product's pack size, for the unit price.

Existing products get a size from their name straight away; the next check
fills in the rest from the store page.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from price_diaries.parsers.size_text import parse_size

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("size_amount", sa.Float(), nullable=True))
        batch.add_column(sa.Column("size_unit", sa.String(3), nullable=True))
        batch.add_column(sa.Column("size_source", sa.String(4), nullable=True))

    conn = op.get_bind()
    for product_id, name in conn.execute(sa.text("SELECT id, name FROM products")).all():
        size = parse_size(name)
        if size is not None:
            conn.execute(
                sa.text(
                    "UPDATE products SET size_amount = :amount, size_unit = :unit, "
                    "size_source = 'name' WHERE id = :id"
                ),
                {"amount": size.amount, "unit": size.unit, "id": product_id},
            )


def downgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.drop_column("size_source")
        batch.drop_column("size_unit")
        batch.drop_column("size_amount")
