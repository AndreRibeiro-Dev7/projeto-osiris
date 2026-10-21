"""add secure owner password recovery

Revision ID: 2c3d4e5f6a7b
Revises: 1b2c3d4e5f6a
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2c3d4e5f6a7b"
down_revision: str | Sequence[str] | None = "1b2c3d4e5f6a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_reset_code_hash", sa.String(64)))
    op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("password_reset_requested_at", sa.DateTime(timezone=True)))
    op.add_column(
        "users",
        sa.Column(
            "password_reset_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("auth_version", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "auth_version")
    op.drop_column("users", "password_reset_attempts")
    op.drop_column("users", "password_reset_requested_at")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_code_hash")
