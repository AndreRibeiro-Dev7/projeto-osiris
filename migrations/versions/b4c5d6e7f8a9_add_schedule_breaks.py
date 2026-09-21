"""add schedule breaks

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision: str = "b4c5d6e7f8a9"
down_revision: str | Sequence[str] | None = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.add_column("barber_schedules", sa.Column("break_starts_at", sa.Time(), nullable=True))
    op.add_column("barber_schedules", sa.Column("break_ends_at", sa.Time(), nullable=True))
def downgrade() -> None:
    op.drop_column("barber_schedules", "break_ends_at")
    op.drop_column("barber_schedules", "break_starts_at")
