"""Dashboard-focused models: data connections, summaries, watchlists, and alerts."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PatientDataConnection(Base, TimestampMixin):
    """Connection metadata for external medical data providers."""

    __tablename__ = "patient_data_connections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="connected",
        comment="connected|syncing|error|disconnected",
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_count: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "patient_id",
            "provider_slug",
            name="uq_patient_data_connections_patient_provider",
        ),
        Index(
            "ix_patient_data_connections_patient_status",
            "patient_id",
            "status",
        ),
    )


class PatientMetricDailySummary(Base, TimestampMixin):
    """Daily materialized snapshot of latest metric state per patient."""

    __tablename__ = "patient_metric_daily_summary"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    metric_key: Mapped[str] = mapped_column(String(120), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(200), nullable=False)
    value_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    normalized_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalized_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="in_range",
        comment="in_range|out_of_range",
    )
    direction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trend_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="lab_result",
    )
    source_id: Mapped[int | None] = mapped_column(nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_label: Mapped[str | None] = mapped_column(String(16), nullable=True)
    freshness_days: Mapped[int | None] = mapped_column(nullable=True)
    excluded_from_insights: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "patient_id",
            "summary_date",
            "metric_key",
            name="uq_metric_daily_summary_patient_date_metric",
        ),
        Index(
            "ix_metric_daily_summary_patient_date",
            "patient_id",
            "summary_date",
        ),
        Index(
            "ix_metric_daily_summary_patient_metric",
            "patient_id",
            "metric_key",
        ),
    )


class PatientWatchMetric(Base, TimestampMixin):
    """User-selected metrics to monitor for threshold/range changes."""

    __tablename__ = "patient_watch_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_key: Mapped[str] = mapped_column(String(120), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(200), nullable=False)
    lower_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    direction: Mapped[str] = mapped_column(
        String(12),
        nullable=False,
        default="both",
        comment="above|below|both",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "patient_id",
            "metric_key",
            name="uq_patient_watch_metrics_patient_metric",
        ),
        Index("ix_patient_watch_metrics_patient_active", "patient_id", "is_active"),
    )


class PatientMetricAlert(Base, TimestampMixin):
    """Generated metric alerts linked to watchlist rules and record evidence."""

    __tablename__ = "patient_metric_alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    watch_metric_id: Mapped[int | None] = mapped_column(
        ForeignKey("patient_watch_metrics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    metric_key: Mapped[str] = mapped_column(String(120), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(200), nullable=False)
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    previous_numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    previous_value_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    trend_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    alert_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="threshold",
        comment="threshold|abnormal|trend_change",
    )
    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="info",
        comment="info|warning|critical",
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="lab_result",
    )
    source_id: Mapped[int | None] = mapped_column(nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    previous_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_patient_metric_alerts_patient_ack", "patient_id", "acknowledged"),
        Index("ix_patient_metric_alerts_metric_key", "metric_key"),
    )


class PatientConnectionSyncEvent(Base, TimestampMixin):
    """Audit events for provider connection state and sync lifecycle."""

    __tablename__ = "patient_connection_sync_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[int | None] = mapped_column(
        ForeignKey("patient_data_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="updated",
        comment="connected|disconnected|sync_started|sync_completed|sync_failed|updated",
    )
    status_before: Mapped[str | None] = mapped_column(String(24), nullable=True)
    status_after: Mapped[str | None] = mapped_column(String(24), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        Index("ix_connection_sync_events_patient_created", "patient_id", "created_at"),
        Index("ix_connection_sync_events_provider", "patient_id", "provider_slug"),
    )
