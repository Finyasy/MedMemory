"""Schemas for Apple Health sync (MVP: daily steps only)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class AppleHealthStepDayIn(BaseModel):
    """Single daily step total from Apple Health (aggregated by the iOS client)."""

    sample_date: date = Field(..., description="Local calendar date for the step total")
    step_count: int = Field(..., ge=0, le=500_000)
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: str | None = Field(default=None, max_length=64)
    source_name: str | None = Field(default="Apple Health", max_length=120)
    source_bundle_id: str | None = Field(default=None, max_length=160)
    source_uuid: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validate_interval(self) -> "AppleHealthStepDayIn":
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValueError("end_at must be greater than or equal to start_at")
        return self


class AppleHealthStepsSyncRequest(BaseModel):
    """Batch sync request from iOS HealthKit client."""

    samples: list[AppleHealthStepDayIn] = Field(default_factory=list)
    client_anchor: str | None = Field(default=None, max_length=255)
    sync_started_at: datetime | None = None
    sync_completed_at: datetime | None = None
    device_name: str | None = Field(default=None, max_length=120)
    app_version: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def validate_sync_window(self) -> "AppleHealthStepsSyncRequest":
        if (
            self.sync_started_at
            and self.sync_completed_at
            and self.sync_completed_at < self.sync_started_at
        ):
            raise ValueError("sync_completed_at must be >= sync_started_at")
        return self


class AppleHealthStepsSyncResponse(BaseModel):
    patient_id: int
    provider_slug: str = "apple_health"
    received_samples: int
    unique_days_received: int
    inserted_days: int
    updated_days: int
    unchanged_days: int
    latest_sample_date: date | None = None
    last_synced_at: datetime | None = None
    connection_status: str = "connected"
    client_anchor: str | None = None


class AppleHealthStepTrendPoint(BaseModel):
    sample_date: date
    step_count: int
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: str | None = None
    source_name: str | None = None


class AppleHealthStepsTrendResponse(BaseModel):
    patient_id: int
    metric_key: str = "steps"
    metric_name: str = "Steps"
    unit: str = "steps"
    start_date: date
    end_date: date
    points: list[AppleHealthStepTrendPoint]
    total_steps: int = 0
    average_steps: float | None = None
    latest_step_count: int | None = None
    latest_sample_date: date | None = None
    last_synced_at: datetime | None = None


class AppleHealthSyncStatusResponse(BaseModel):
    patient_id: int
    provider_name: str = "Apple Health"
    provider_slug: str = "apple_health"
    status: str = "disconnected"
    is_active: bool = False
    last_synced_at: datetime | None = None
    last_error: str | None = None
    total_synced_days: int = 0
    earliest_sample_date: date | None = None
    latest_sample_date: date | None = None

