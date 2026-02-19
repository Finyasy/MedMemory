"""Add daily materialized metric summary table.

Revision ID: 20260218_00
Revises: 20260217_01
Create Date: 2026-02-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260218_00"
down_revision: str | None = "20260217_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "patient_metric_daily_summary",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("summary_date", sa.Date(), nullable=False),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("metric_name", sa.String(length=200), nullable=False),
        sa.Column("value_text", sa.String(length=100), nullable=True),
        sa.Column("numeric_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("normalized_value", sa.Float(), nullable=True),
        sa.Column("normalized_unit", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="in_range"),
        sa.Column("direction", sa.String(length=32), nullable=True),
        sa.Column("trend_delta", sa.Float(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default="lab_result"),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("provider_name", sa.String(length=200), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("confidence_label", sa.String(length=16), nullable=True),
        sa.Column("freshness_days", sa.Integer(), nullable=True),
        sa.Column(
            "excluded_from_insights",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
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
            "summary_date",
            "metric_key",
            name="uq_metric_daily_summary_patient_date_metric",
        ),
    )
    op.create_index(
        "ix_patient_metric_daily_summary_patient_id",
        "patient_metric_daily_summary",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_metric_daily_summary_summary_date",
        "patient_metric_daily_summary",
        ["summary_date"],
        unique=False,
    )
    op.create_index(
        "ix_metric_daily_summary_patient_date",
        "patient_metric_daily_summary",
        ["patient_id", "summary_date"],
        unique=False,
    )
    op.create_index(
        "ix_metric_daily_summary_patient_metric",
        "patient_metric_daily_summary",
        ["patient_id", "metric_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_metric_daily_summary_patient_metric",
        table_name="patient_metric_daily_summary",
    )
    op.drop_index(
        "ix_metric_daily_summary_patient_date",
        table_name="patient_metric_daily_summary",
    )
    op.drop_index(
        "ix_patient_metric_daily_summary_summary_date",
        table_name="patient_metric_daily_summary",
    )
    op.drop_index(
        "ix_patient_metric_daily_summary_patient_id",
        table_name="patient_metric_daily_summary",
    )
    op.drop_table("patient_metric_daily_summary")
