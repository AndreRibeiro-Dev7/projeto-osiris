"""add customer loyalty redemptions

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column(
            "loyalty_rewards_redeemed",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_customers_loyalty_rewards_redeemed_non_negative",
        "customers",
        "loyalty_rewards_redeemed >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_customers_loyalty_rewards_redeemed_non_negative",
        "customers",
        type_="check",
    )
    op.drop_column("customers", "loyalty_rewards_redeemed")
