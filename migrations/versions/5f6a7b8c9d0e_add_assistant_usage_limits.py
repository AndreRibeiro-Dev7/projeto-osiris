"""add shared assistant request limits

Revision ID: 5f6a7b8c9d0e
Revises: 4e5f6a7b8c9d
"""

import sqlalchemy as sa
from alembic import op

revision = "5f6a7b8c9d0e"
down_revision = "4e5f6a7b8c9d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_usage_limits",
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
    op.drop_table("assistant_usage_limits")
