"""add appointment public tokens

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column(
            "public_token",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_appointments_public_token", "appointments", ["public_token"]
    )
    op.alter_column("appointments", "public_token", server_default=None)


def downgrade() -> None:
    op.drop_constraint("uq_appointments_public_token", "appointments", type_="unique")
    op.drop_column("appointments", "public_token")
