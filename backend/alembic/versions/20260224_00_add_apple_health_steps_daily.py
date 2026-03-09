"""Add Apple Health daily step sync table.

Revision ID: 20260224_00
Revises: 20260218_00
Create Date: 2026-02-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260224_00"
down_revision: str | None = "20260218_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "patient_apple_health_steps_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("sample_date", sa.Date(), nullable=False),
        sa.Column("step_count", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("source_name", sa.String(length=120), nullable=True),
        sa.Column("source_bundle_id", sa.String(length=160), nullable=True),
        sa.Column("source_uuid", sa.String(length=160), nullable=True),
        sa.Column("sync_anchor", sa.String(length=255), nullable=True),
        sa.Column("ingest_note", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "patient_id",
            "sample_date",
            name="uq_patient_apple_steps_patient_date",
        ),
    )
    op.create_index(
        "ix_patient_apple_health_steps_daily_patient_id",
        "patient_apple_health_steps_daily",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_apple_health_steps_daily_sample_date",
        "patient_apple_health_steps_daily",
        ["sample_date"],
        unique=False,
    )
    op.create_index(
        "ix_patient_apple_steps_patient_date",
        "patient_apple_health_steps_daily",
        ["patient_id", "sample_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_patient_apple_steps_patient_date",
        table_name="patient_apple_health_steps_daily",
    )
    op.drop_index(
        "ix_patient_apple_health_steps_daily_sample_date",
        table_name="patient_apple_health_steps_daily",
    )
    op.drop_index(
        "ix_patient_apple_health_steps_daily_patient_id",
        table_name="patient_apple_health_steps_daily",
    )
    op.drop_table("patient_apple_health_steps_daily")
