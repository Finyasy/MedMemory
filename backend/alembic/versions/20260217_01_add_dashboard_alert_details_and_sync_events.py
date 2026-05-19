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


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    alert_columns = _columns("patient_metric_alerts")
    if _table_exists("patient_connection_sync_events") and {
        "previous_numeric_value",
        "previous_value_text",
        "trend_delta",
        "alert_kind",
        "previous_observed_at",
    }.issubset(alert_columns):
        return

    op.execute(
        sa.text(
            "ALTER TABLE patient_metric_alerts ADD COLUMN IF NOT EXISTS "
            "previous_numeric_value DOUBLE PRECISION"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE patient_metric_alerts ADD COLUMN IF NOT EXISTS "
            "previous_value_text VARCHAR(100)"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE patient_metric_alerts ADD COLUMN IF NOT EXISTS "
            "trend_delta DOUBLE PRECISION"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE patient_metric_alerts ADD COLUMN IF NOT EXISTS "
            "alert_kind VARCHAR(32) NOT NULL DEFAULT 'threshold'"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE patient_metric_alerts ADD COLUMN IF NOT EXISTS "
            "previous_observed_at TIMESTAMP WITH TIME ZONE"
        )
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
