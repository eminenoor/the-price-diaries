"""Notes in the inbox, and the alert states that keep each one from repeating.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("old_price", sa.Float()),
        sa.Column("new_price", sa.Float()),
        sa.Column("other_store", sa.String(32)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime()),
    )
    op.create_index("ix_notifications_product_id", "notifications", ["product_id"])

    op.create_table(
        "alert_states",
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("kind", sa.String(16), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("price", sa.Float()),
    )


def downgrade() -> None:
    op.drop_table("alert_states")
    op.drop_index("ix_notifications_product_id", table_name="notifications")
    op.drop_table("notifications")
