"""Add resource availability and absences tables.

Revision ID: 20241105_0005
Revises: 20241104_0004
Create Date: 2024-11-05 10:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20241105_0005"
down_revision: Union[str, None] = "20241104_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resource",
        sa.Column("availability_template", sa.JSON(), nullable=True),
    )
    op.add_column(
        "resource",
        sa.Column("preferred_shift_codes", sa.JSON(), nullable=True),
    )
    op.add_column(
        "resource",
        sa.Column("undesired_shift_codes", sa.JSON(), nullable=True),
    )

    op.create_table(
        "resourceabsence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "resource_id",
            sa.Integer(),
            sa.ForeignKey("resource.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("absence_type", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("resourceabsence")
    op.drop_column("resource", "undesired_shift_codes")
    op.drop_column("resource", "preferred_shift_codes")
    op.drop_column("resource", "availability_template")
