"""add immutable business activity history

Revision ID: 1b2c3d4e5f6a
Revises: 0a1b2c3d4e5f
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1b2c3d4e5f6a"
down_revision: str | Sequence[str] | None = "0a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_email", sa.String(length=254), nullable=False),
        sa.Column("actor_role", sa.String(length=20), nullable=False),
        sa.Column("actor_is_primary_owner", sa.Boolean(), nullable=False),
        sa.Column("area", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_business_id", "audit_logs", ["business_id"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_area", "audit_logs", ["area"])
    op.create_index(
        "ix_audit_logs_business_created_at",
        "audit_logs",
        ["business_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_business_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_area", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_business_id", table_name="audit_logs")
    op.drop_table("audit_logs")
