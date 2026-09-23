"""add barber accounts

Revision ID: f7b8c9d0e1f2
Revises: e6f7a8b9c0d1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add roles and optional professional links to authenticated accounts."""
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), server_default="owner", nullable=False),
    )
    op.add_column("users", sa.Column("barber_id", sa.Uuid(), nullable=True))
    op.create_check_constraint("ck_users_role", "users", "role IN ('owner', 'barber')")
    op.create_foreign_key(
        "fk_users_barber_id",
        "users",
        "barbers",
        ["barber_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint("uq_users_barber_id", "users", ["barber_id"])


def downgrade() -> None:
    """Remove professional login support."""
    op.drop_constraint("uq_users_barber_id", "users", type_="unique")
    op.drop_constraint("fk_users_barber_id", "users", type_="foreignkey")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "barber_id")
    op.drop_column("users", "role")
