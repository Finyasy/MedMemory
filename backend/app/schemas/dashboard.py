"""Schemas for dashboard connections, highlights, metrics, and alerts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DataConnectionBase(BaseModel):
    provider_name: str = Field(..., min_length=1, max_length=120)
    provider_slug: str = Field(..., min_length=1, max_length=80)


class DataConnectionUpsert(DataConnectionBase):
    status: str = Field(
        default="connected",
        pattern="^(connected|syncing|error|disconnected)$",
    )
    source_count: int = Field(default=0, ge=0)
    last_error: str | None = None
    last_synced_at: datetime | None = None
    is_active: bool = True


class DataConnectionResponse(DataConnectionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    status: str
    source_count: int
    last_error: str | None = None
    last_synced_at: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DashboardSummary(BaseModel):
    out_of_range: int
    in_range: int
    tracked_metrics: int
    last_updated_at: datetime | None = None


class HighlightItem(BaseModel):
    metric_key: str
    metric_name: str
    value: str | None = None
    numeric_value: float | None = None
    unit: str | None = None
    observed_at: datetime | None = None
    status: str
    direction: str | None = None
    trend_delta: float | None = None
    reference_range: str | None = None
    risk_priority_score: float = 0.0
    risk_priority_reason: str | None = None
    source_type: str
    source_id: int | None = None
    provider_name: str | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_label: str | None = None
    freshness_days: int | None = Field(default=None, ge=0)


class DashboardHighlightsResponse(BaseModel):
    patient_id: int
    summary: DashboardSummary
    highlights: list[HighlightItem]


class MetricTrendPoint(BaseModel):
    value: float | None = None
    value_text: str | None = None
    raw_value: float | None = None
    raw_value_text: str | None = None
    raw_unit: str | None = None
    normalized_value: float | None = None
    normalized_value_text: str | None = None
    normalized_unit: str | None = None
    observed_at: datetime | None = None
    source_type: str | None = None
    source_id: int | None = None
    provider_name: str | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_label: str | None = None
    freshness_days: int | None = Field(default=None, ge=0)
    excluded_from_insights: bool = False
    exclusion_reason: str | None = None


class MetricDetailResponse(BaseModel):
    patient_id: int
    metric_key: str
    metric_name: str
    latest_value: str | None = None
    latest_numeric_value: float | None = None
    unit: str | None = None
    observed_at: datetime | None = None
    reference_range: str | None = None
    range_min: float | None = None
    range_max: float | None = None
    in_range: bool | None = None
    about: str
    latest_source_type: str | None = None
    latest_source_id: int | None = None
    normalized_unit: str | None = None
    latest_normalized_value: float | None = None
    latest_normalized_value_text: str | None = None
    normalization_applied: bool = False
    latest_confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    latest_confidence_label: str | None = None
    latest_freshness_days: int | None = Field(default=None, ge=0)
    excluded_points_count: int = Field(default=0, ge=0)
    trend: list[MetricTrendPoint]


class WatchMetricBase(BaseModel):
    metric_name: str = Field(..., min_length=1, max_length=200)
    metric_key: str = Field(..., min_length=1, max_length=120)
    lower_bound: float | None = None
    upper_bound: float | None = None
    direction: str = Field(default="both", pattern="^(above|below|both)$")
    is_active: bool = True


class WatchMetricCreate(WatchMetricBase):
    pass


class WatchMetricUpdate(BaseModel):
    metric_name: str | None = Field(None, min_length=1, max_length=200)
    metric_key: str | None = Field(None, min_length=1, max_length=120)
    lower_bound: float | None = None
    upper_bound: float | None = None
    direction: str | None = Field(None, pattern="^(above|below|both)$")
    is_active: bool | None = None


class WatchMetricResponse(WatchMetricBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    created_at: datetime
    updated_at: datetime


class MetricAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    watch_metric_id: int | None = None
    metric_key: str
    metric_name: str
    numeric_value: float | None = None
    value_text: str | None = None
    previous_numeric_value: float | None = None
    previous_value_text: str | None = None
    unit: str | None = None
    trend_delta: float | None = None
    alert_kind: str
    severity: str
    reason: str
    source_type: str
    source_id: int | None = None
    observed_at: datetime | None = None
    previous_observed_at: datetime | None = None
    acknowledged: bool
    acknowledged_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AlertsEvaluateResponse(BaseModel):
    generated: int
    total_active_unacknowledged: int


class ConnectionSyncEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    connection_id: int | None = None
    provider_slug: str
    event_type: str
    status_before: str | None = None
    status_after: str | None = None
    details: str | None = None
    last_error: str | None = None
    triggered_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime


class ConnectionSyncDryRunResponse(BaseModel):
    ok: bool
    mode: str
    provider_key: str | None = None
    base_url: str | None = None
    patient_ref: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    details: str
    checked_at: datetime
