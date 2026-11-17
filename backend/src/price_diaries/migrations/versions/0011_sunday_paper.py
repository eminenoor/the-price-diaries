"""The Sunday paper: a weekly note with no product, and a record of failed checks.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite can't change a column in place, so batch mode copies the table.
    with op.batch_alter_table("notifications") as batch:
        batch.alter_column("product_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("week", sa.Date()))
        batch.create_index("ux_notifications_kind_week", ["kind", "week"], unique=True)

    op.create_table(
        "check_failures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("error", sa.String(500), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_check_failures_product_time", "check_failures", ["product_id", "checked_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_check_failures_product_time", table_name="check_failures")
    op.drop_table("check_failures")
    op.execute("DELETE FROM notifications WHERE product_id IS NULL")
    with op.batch_alter_table("notifications") as batch:
        batch.drop_index("ux_notifications_kind_week")
        batch.drop_column("week")
        batch.alter_column("product_id", existing_type=sa.Integer(), nullable=False)
