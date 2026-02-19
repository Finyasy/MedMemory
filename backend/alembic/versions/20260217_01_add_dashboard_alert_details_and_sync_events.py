"""Add dashboard alert detail columns and connection sync audit events.

Revision ID: 20260217_01
Revises: 20260217_00
Create Date: 2026-02-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260217_01"
down_revision: str | None = "20260217_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "patient_metric_alerts",
        sa.Column("previous_numeric_value", sa.Float(), nullable=True),
    )
    op.add_column(
        "patient_metric_alerts",
        sa.Column("previous_value_text", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "patient_metric_alerts",
        sa.Column("trend_delta", sa.Float(), nullable=True),
    )
    op.add_column(
        "patient_metric_alerts",
        sa.Column(
            "alert_kind",
            sa.String(length=32),
            nullable=False,
            server_default="threshold",
        ),
    )
    op.add_column(
        "patient_metric_alerts",
        sa.Column("previous_observed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "patient_connection_sync_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=True),
        sa.Column("provider_slug", sa.String(length=80), nullable=False),
        sa.Column(
            "event_type", sa.String(length=32), nullable=False, server_default="updated"
        ),
        sa.Column("status_before", sa.String(length=24), nullable=True),
        sa.Column("status_after", sa.String(length=24), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
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
            ["connection_id"],
            ["patient_data_connections.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_patient_connection_sync_events_patient_id",
        "patient_connection_sync_events",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_connection_sync_events_connection_id",
        "patient_connection_sync_events",
        ["connection_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_connection_sync_events_triggered_by_user_id",
        "patient_connection_sync_events",
        ["triggered_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_connection_sync_events_patient_created",
        "patient_connection_sync_events",
        ["patient_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_connection_sync_events_provider",
        "patient_connection_sync_events",
        ["patient_id", "provider_slug"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_connection_sync_events_provider",
        table_name="patient_connection_sync_events",
    )
    op.drop_index(
        "ix_connection_sync_events_patient_created",
        table_name="patient_connection_sync_events",
    )
    op.drop_index(
        "ix_patient_connection_sync_events_triggered_by_user_id",
        table_name="patient_connection_sync_events",
    )
    op.drop_index(
        "ix_patient_connection_sync_events_connection_id",
        table_name="patient_connection_sync_events",
    )
    op.drop_index(
        "ix_patient_connection_sync_events_patient_id",
        table_name="patient_connection_sync_events",
    )
    op.drop_table("patient_connection_sync_events")

    op.drop_column("patient_metric_alerts", "previous_observed_at")
    op.drop_column("patient_metric_alerts", "alert_kind")
    op.drop_column("patient_metric_alerts", "trend_delta")
    op.drop_column("patient_metric_alerts", "previous_value_text")
    op.drop_column("patient_metric_alerts", "previous_numeric_value")
