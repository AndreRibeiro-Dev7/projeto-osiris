"""mark the original account as primary owner

Revision ID: 0a1b2c3d4e5f
Revises: f7b8c9d0e1f2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = "f7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the hierarchy flag and promote the oldest owner of each business."""
    op.add_column(
        "users",
        sa.Column(
            "is_primary_owner",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET is_primary_owner = TRUE
            WHERE id IN (
                SELECT DISTINCT ON (business_id) id
                FROM users
                WHERE role = 'owner'
                ORDER BY business_id, created_at, id
            )
            """
        )
    )
    op.create_index(
        "uq_users_primary_owner_per_business",
        "users",
        ["business_id"],
        unique=True,
        postgresql_where=sa.text("is_primary_owner = TRUE"),
        sqlite_where=sa.text("is_primary_owner = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_primary_owner_per_business", table_name="users")
    op.drop_column("users", "is_primary_owner")
