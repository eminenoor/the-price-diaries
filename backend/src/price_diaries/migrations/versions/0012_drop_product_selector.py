"""Drop the per-product CSS selector: the UI never set it, and every store has its own.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.drop_column("selector")


def downgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("selector", sa.String(300), nullable=True))
