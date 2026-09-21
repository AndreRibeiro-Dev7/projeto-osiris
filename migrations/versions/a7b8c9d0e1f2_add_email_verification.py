"""add email change verification fields

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("pending_email", sa.String(length=254), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_verification_code_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verification_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "email_verification_expires_at")
    op.drop_column("users", "email_verification_code_hash")
    op.drop_column("users", "pending_email")
