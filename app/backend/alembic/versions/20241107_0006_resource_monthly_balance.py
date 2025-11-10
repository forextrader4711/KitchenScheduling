"""add resource monthly balance table

Revision ID: 20241107_0006
Revises: 20241105_0005
Create Date: 2024-11-07 00:06:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20241107_0006"
down_revision: str = "20241105_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resource_monthly_balance",
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("opening_hours", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("closing_hours", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["resource_id"], ["resource.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("resource_id", "month"),
    )
    op.create_index(
        op.f("ix_resource_monthly_balance_resource_id"),
        "resource_monthly_balance",
        ["resource_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_resource_monthly_balance_resource_id"), table_name="resource_monthly_balance")
    op.drop_table("resource_monthly_balance")
