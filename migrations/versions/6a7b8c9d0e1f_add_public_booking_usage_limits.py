"""add shared public booking request limits

Revision ID: 6a7b8c9d0e1f
Revises: 5f6a7b8c9d0e
"""

import sqlalchemy as sa
from alembic import op

revision = "6a7b8c9d0e1f"
down_revision = "5f6a7b8c9d0e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_booking_usage_limits",
        sa.Column(
            "business_id",
            sa.Uuid(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("minute_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("minute_requests", sa.Integer(), nullable=False),
        sa.Column("hour_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hour_requests", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("public_booking_usage_limits")
