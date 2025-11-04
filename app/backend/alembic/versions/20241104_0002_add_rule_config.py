"""Add scheduling rule configuration table.

Revision ID: 20241104_0002
Revises: 20241102_0001
Create Date: 2024-11-04 12:40:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20241104_0002"
down_revision = "20241102_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedulingruleconfig",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_table("schedulingruleconfig")
