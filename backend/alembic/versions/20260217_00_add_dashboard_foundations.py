"""Add dashboard foundation tables for connections, watchlists, and alerts.

Revision ID: 20260217_00
Revises: 20260214_00
Create Date: 2026-02-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260217_00"
down_revision: str | None = "20260214_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "patient_data_connections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(length=120), nullable=False),
        sa.Column("provider_slug", sa.String(length=80), nullable=False),
        sa.Column(
            "status", sa.String(length=24), nullable=False, server_default="connected"
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
            "provider_slug",
            name="uq_patient_data_connections_patient_provider",
        ),
    )
    op.create_index(
        "ix_patient_data_connections_patient_id",
        "patient_data_connections",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_data_connections_patient_status",
        "patient_data_connections",
        ["patient_id", "status"],
        unique=False,
    )

    op.create_table(
        "patient_watch_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("metric_name", sa.String(length=200), nullable=False),
        sa.Column("lower_bound", sa.Float(), nullable=True),
        sa.Column("upper_bound", sa.Float(), nullable=True),
        sa.Column(
            "direction", sa.String(length=12), nullable=False, server_default="both"
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
            "metric_key",
            name="uq_patient_watch_metrics_patient_metric",
        ),
    )
    op.create_index(
        "ix_patient_watch_metrics_patient_id",
        "patient_watch_metrics",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_watch_metrics_patient_active",
        "patient_watch_metrics",
        ["patient_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "patient_metric_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("watch_metric_id", sa.Integer(), nullable=True),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("metric_name", sa.String(length=200), nullable=False),
        sa.Column("numeric_value", sa.Float(), nullable=True),
        sa.Column("value_text", sa.String(length=100), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column(
            "severity", sa.String(length=16), nullable=False, server_default="info"
        ),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column(
            "source_type",
            sa.String(length=40),
            nullable=False,
            server_default="lab_result",
        ),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["watch_metric_id"],
            ["patient_watch_metrics.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_patient_metric_alerts_patient_id",
        "patient_metric_alerts",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_metric_alerts_watch_metric_id",
        "patient_metric_alerts",
        ["watch_metric_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_metric_alerts_patient_ack",
        "patient_metric_alerts",
        ["patient_id", "acknowledged"],
        unique=False,
    )
    op.create_index(
        "ix_patient_metric_alerts_metric_key",
        "patient_metric_alerts",
        ["metric_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_patient_metric_alerts_metric_key", table_name="patient_metric_alerts"
    )
    op.drop_index(
        "ix_patient_metric_alerts_patient_ack", table_name="patient_metric_alerts"
    )
    op.drop_index(
        "ix_patient_metric_alerts_watch_metric_id", table_name="patient_metric_alerts"
    )
    op.drop_index(
        "ix_patient_metric_alerts_patient_id", table_name="patient_metric_alerts"
    )
    op.drop_table("patient_metric_alerts")

    op.drop_index(
        "ix_patient_watch_metrics_patient_active", table_name="patient_watch_metrics"
    )
    op.drop_index(
        "ix_patient_watch_metrics_patient_id", table_name="patient_watch_metrics"
    )
    op.drop_table("patient_watch_metrics")

    op.drop_index(
        "ix_patient_data_connections_patient_status",
        table_name="patient_data_connections",
    )
    op.drop_index(
        "ix_patient_data_connections_patient_id",
        table_name="patient_data_connections",
    )
    op.drop_table("patient_data_connections")
