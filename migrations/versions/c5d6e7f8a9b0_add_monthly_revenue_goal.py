"""add monthly revenue goal

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision: str = "c5d6e7f8a9b0"
down_revision: str | Sequence[str] | None = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.add_column("businesses", sa.Column("monthly_revenue_goal_cents", sa.Integer(), server_default="0", nullable=False))
def downgrade() -> None:
    op.drop_column("businesses", "monthly_revenue_goal_cents")
