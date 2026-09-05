"""add barber schedules

Revision ID: 8f0a1c2d3e4f
Revises: 273e24d3eef6
Create Date: 2026-09-04 22:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8f0a1c2d3e4f"
down_revision: str | Sequence[str] | None = "273e24d3eef6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create recurring weekly schedules for barbers."""
    op.create_table(
        "barber_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("barber_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.Time(), nullable=False),
        sa.Column("ends_at", sa.Time(), nullable=False),
        sa.Column("slot_duration_minutes", sa.Integer(), nullable=False),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_barber_schedules_weekday"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_barber_schedules_valid_time_range"),
        sa.CheckConstraint(
            "slot_duration_minutes BETWEEN 5 AND 480",
            name="ck_barber_schedules_slot_duration",
        ),
        sa.ForeignKeyConstraint(["barber_id"], ["barbers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("barber_id", "weekday", name="uq_barber_schedules_barber_weekday"),
    )


def downgrade() -> None:
    """Remove recurring weekly schedules."""
    op.drop_table("barber_schedules")
