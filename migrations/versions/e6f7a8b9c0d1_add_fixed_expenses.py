"""add fixed expenses

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
"""

from alembic import op
import sqlalchemy as sa

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("is_fixed", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column("expenses", "is_fixed")
