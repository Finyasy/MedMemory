"""Add clinician copilot run persistence tables.

Revision ID: 20260307_00
Revises: 20260224_00
Create Date: 2026-03-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260307_00"
down_revision: str | None = "20260224_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clinician_agent_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("clinician_user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("template", sa.String(length=64), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("final_answer", sa.Text(), nullable=True),
        sa.Column("final_citations_json", sa.Text(), nullable=True),
        sa.Column("safety_flags_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clinician_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_clinician_agent_runs_patient_id",
        "clinician_agent_runs",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_clinician_agent_runs_clinician_user_id",
        "clinician_agent_runs",
        ["clinician_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_clinician_agent_runs_patient_created",
        "clinician_agent_runs",
        ["patient_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_clinician_agent_runs_clinician_created",
        "clinician_agent_runs",
        ["clinician_user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "clinician_agent_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("input_json", sa.Text(), nullable=True),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("citations_json", sa.Text(), nullable=True),
        sa.Column("safety_flags_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["clinician_agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_clinician_agent_steps_run_id",
        "clinician_agent_steps",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_clinician_agent_steps_run_order",
        "clinician_agent_steps",
        ["run_id", "step_order"],
        unique=False,
    )

    op.create_table(
        "clinician_agent_suggestions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("suggestion_order", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("action_label", sa.String(length=80), nullable=True),
        sa.Column("action_target", sa.String(length=160), nullable=True),
        sa.Column("citations_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["clinician_agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_clinician_agent_suggestions_run_id",
        "clinician_agent_suggestions",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_clinician_agent_suggestions_run_order",
        "clinician_agent_suggestions",
        ["run_id", "suggestion_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_clinician_agent_suggestions_run_order",
        table_name="clinician_agent_suggestions",
    )
    op.drop_index(
        "ix_clinician_agent_suggestions_run_id",
        table_name="clinician_agent_suggestions",
    )
    op.drop_table("clinician_agent_suggestions")

    op.drop_index(
        "ix_clinician_agent_steps_run_order",
        table_name="clinician_agent_steps",
    )
    op.drop_index(
        "ix_clinician_agent_steps_run_id",
        table_name="clinician_agent_steps",
    )
    op.drop_table("clinician_agent_steps")

    op.drop_index(
        "ix_clinician_agent_runs_clinician_created",
        table_name="clinician_agent_runs",
    )
    op.drop_index(
        "ix_clinician_agent_runs_patient_created",
        table_name="clinician_agent_runs",
    )
    op.drop_index(
        "ix_clinician_agent_runs_clinician_user_id",
        table_name="clinician_agent_runs",
    )
    op.drop_index(
        "ix_clinician_agent_runs_patient_id",
        table_name="clinician_agent_runs",
    )
    op.drop_table("clinician_agent_runs")
