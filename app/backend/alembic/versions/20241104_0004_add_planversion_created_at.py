"""Add created_at to planversion.

Revision ID: 20241104_0004
Revises: 20241104_0003
Create Date: 2024-11-04 13:25:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20241104_0004"
down_revision = "20241104_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "planversion",
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_column("planversion", "created_at")
