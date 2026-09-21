"""add assistant conversations

Revision ID: 9a1b2c3d4e5f
Revises: 8f0a1c2d3e4f
Create Date: 2026-09-06 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = "8f0a1c2d3e4f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create persisted slot proposals awaiting confirmation."""
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("barber_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("proposed_starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("proposed_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["barber_id"], ["barbers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Remove assistant booking conversations."""
    op.drop_table("assistant_conversations")
