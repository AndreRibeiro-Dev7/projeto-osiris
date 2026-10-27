"""add persistent WhatsApp booking recovery

Revision ID: 4e5f6a7b8c9d
Revises: 3d4e5f6a7b8c
"""

import sqlalchemy as sa
from alembic import op

revision = "4e5f6a7b8c9d"
down_revision = "3d4e5f6a7b8c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "booking_access_challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "business_id",
            sa.Uuid(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("code_hash", sa.String(64)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_sent_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
    )
    op.create_table(
        "booking_access_throttles",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("booking_access_throttles")
    op.drop_table("booking_access_challenges")
