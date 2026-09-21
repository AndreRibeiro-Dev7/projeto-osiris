"""add barber commissions

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "barbers",
        sa.Column(
            "commission_percentage",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_barbers_commission_percentage",
        "barbers",
        "commission_percentage BETWEEN 0 AND 100",
    )


def downgrade() -> None:
    op.drop_constraint("ck_barbers_commission_percentage", "barbers", type_="check")
    op.drop_column("barbers", "commission_percentage")
