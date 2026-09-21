"""add business closures

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision: str = "a3b4c5d6e7f8"
down_revision: str | Sequence[str] | None = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.create_table("business_closures", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("business_id", sa.Uuid(), nullable=False), sa.Column("closure_date", sa.Date(), nullable=False), sa.Column("reason", sa.String(200), nullable=False), sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("business_id", "closure_date", name="uq_business_closures_date"))
def downgrade() -> None: op.drop_table("business_closures")
