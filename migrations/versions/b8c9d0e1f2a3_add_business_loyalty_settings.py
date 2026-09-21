"""add business loyalty settings

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column("loyalty_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "businesses",
        sa.Column("loyalty_target", sa.Integer(), server_default="10", nullable=False),
    )
    op.add_column(
        "businesses",
        sa.Column(
            "loyalty_reward",
            sa.String(length=120),
            server_default="1 atendimento grátis",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_businesses_loyalty_target", "businesses", "loyalty_target BETWEEN 2 AND 50"
    )


def downgrade() -> None:
    op.drop_constraint("ck_businesses_loyalty_target", "businesses", type_="check")
    op.drop_column("businesses", "loyalty_reward")
    op.drop_column("businesses", "loyalty_target")
    op.drop_column("businesses", "loyalty_enabled")
