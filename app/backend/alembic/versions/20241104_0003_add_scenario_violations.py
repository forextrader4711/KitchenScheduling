"""Add violations column to PlanScenario.

Revision ID: 20241104_0003
Revises: 20241104_0002
Create Date: 2024-11-04 12:55:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20241104_0003"
down_revision = "20241104_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("planscenario", sa.Column("violations", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    op.drop_column("planscenario", "violations")
