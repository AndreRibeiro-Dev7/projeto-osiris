"""add barber time off

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "barber_time_off",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("barber_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_barber_time_off_valid_range"),
        sa.ForeignKeyConstraint(["barber_id"], ["barbers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("barber_time_off")
