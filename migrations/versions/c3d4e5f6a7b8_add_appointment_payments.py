"""add appointment payments

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    payment_method = sa.Enum("pix", "cash", "credit_card", "debit_card", name="payment_method")
    payment_method.create(op.get_bind(), checkfirst=True)
    op.add_column("appointments", sa.Column("payment_method", payment_method, nullable=True))
    op.add_column("appointments", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("appointments", "paid_at")
    op.drop_column("appointments", "payment_method")
    sa.Enum(name="payment_method").drop(op.get_bind(), checkfirst=True)
