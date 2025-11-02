"""Initial schema for kitchen scheduling domain.

Revision ID: 20241102_0001
Revises:
Create Date: 2024-11-02 15:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241102_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    resource_role_enum = sa.Enum(
        "cook",
        "kitchen_assistant",
        "pot_washer",
        "apprentice",
        "relief_cook",
        name="resourcerole",
    )

    op.create_table(
        "resource",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", resource_role_enum, nullable=False),
        sa.Column("availability_percent", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("contract_hours_per_month", sa.Numeric(5, 2), nullable=False),
        sa.Column("preferred_days_off", sa.String(length=120), nullable=True),
        sa.Column("vacation_days", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=5), nullable=False, server_default=sa.text("'en'")),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "shift",
        sa.Column("code", sa.Integer(), primary_key=True),
        sa.Column("description", sa.String(length=120), nullable=False),
        sa.Column("start", sa.String(length=5), nullable=False),
        sa.Column("end", sa.String(length=5), nullable=False),
        sa.Column("hours", sa.Numeric(4, 2), nullable=False),
    )

    op.create_table(
        "shiftprimerule",
        sa.Column(
            "shift_code",
            sa.Integer(),
            sa.ForeignKey("shift.code", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "monthlyparameters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("contractual_hours", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_vacation_overlap", sa.Integer(), nullable=False),
        sa.Column("publication_deadline", sa.Date(), nullable=False),
    )
    op.create_index(
        "ux_monthlyparameters_month", "monthlyparameters", ["month"], unique=True
    )

    op.create_table(
        "planscenario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False, server_default=sa.text("'Draft'")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_planscenario_month", "planscenario", ["month"], unique=False)

    op.create_table(
        "planversion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "scenario_id",
            sa.Integer(),
            sa.ForeignKey("planscenario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_label", sa.String(length=32), nullable=False, server_default=sa.text("'v1'")),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("published_by", sa.String(length=120), nullable=True),
        sa.Column("summary_hours", sa.Text(), nullable=True),
    )

    op.create_table(
        "planningentry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "resource_id",
            sa.Integer(),
            sa.ForeignKey("resource.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "shift_code",
            sa.Integer(),
            sa.ForeignKey("shift.code"),
            nullable=True,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("absence_type", sa.String(length=32), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "scenario_id",
            sa.Integer(),
            sa.ForeignKey("planscenario.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_planningentry_date", "planningentry", ["date"], unique=False)
    op.create_index(
        "ix_planningentry_resource_id", "planningentry", ["resource_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_planningentry_resource_id", table_name="planningentry")
    op.drop_index("ix_planningentry_date", table_name="planningentry")
    op.drop_table("planningentry")

    op.drop_table("planversion")

    op.drop_index("ix_planscenario_month", table_name="planscenario")
    op.drop_table("planscenario")

    op.drop_index("ux_monthlyparameters_month", table_name="monthlyparameters")
    op.drop_table("monthlyparameters")

    op.drop_table("shiftprimerule")
    op.drop_table("shift")

    op.drop_table("resource")

    resource_role_enum = sa.Enum(
        "cook",
        "kitchen_assistant",
        "pot_washer",
        "apprentice",
        "relief_cook",
        name="resourcerole",
    )
    resource_role_enum.drop(op.get_bind(), checkfirst=True)
