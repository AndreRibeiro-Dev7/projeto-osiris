"""add expense payment status

Revision ID: d5e6f7a8b9c0
Revises: c5d6e7f8a9b0
"""

from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c0"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("is_paid", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("expenses", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("expenses", "paid_at")
    op.drop_column("expenses", "is_paid")
