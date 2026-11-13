"""Remember each product's barcode and its group: the same product at other stores.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("gtin", sa.String(14), nullable=True))
        batch.add_column(sa.Column("group_key", sa.String(24), nullable=True))
        batch.add_column(sa.Column("group_source", sa.String(7), nullable=True))
        batch.create_index("ix_products_group_key", ["group_key"])


def downgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.drop_index("ix_products_group_key")
        batch.drop_column("group_source")
        batch.drop_column("group_key")
        batch.drop_column("gtin")
