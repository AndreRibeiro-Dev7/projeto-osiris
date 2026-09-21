"""add services

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("duration_minutes BETWEEN 5 AND 480", name="ck_services_duration"),
        sa.CheckConstraint("price_cents >= 0", name="ck_services_price"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "name", name="uq_services_business_name"),
    )
    op.add_column("appointments", sa.Column("service_id", sa.Uuid(), nullable=True))
    op.add_column("appointments", sa.Column("price_cents", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_appointments_service_id", "appointments", "services", ["service_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_appointments_service_id", "appointments", type_="foreignkey")
    op.drop_column("appointments", "price_cents")
    op.drop_column("appointments", "service_id")
    op.drop_table("services")
