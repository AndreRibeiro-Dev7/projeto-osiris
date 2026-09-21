"""add customer notes

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: str | Sequence[str] | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "notes")
