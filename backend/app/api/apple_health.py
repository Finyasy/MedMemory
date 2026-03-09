"""Apple Health integration API (MVP: daily step sync and trend reads)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_authorized_patient
from app.database import get_db
from app.models import (
    PatientAppleHealthStepDaily,
    PatientConnectionSyncEvent,
    PatientDataConnection,
    User,
)
from app.schemas.apple_health import (
    AppleHealthStepDayIn,
    AppleHealthStepsSyncRequest,
    AppleHealthStepsSyncResponse,
    AppleHealthStepsTrendResponse,
    AppleHealthStepTrendPoint,
    AppleHealthSyncStatusResponse,
)

router = APIRouter(prefix="/integrations/apple-health", tags=["Apple Health"])
logger = logging.getLogger(__name__)

_APPLE_HEALTH_PROVIDER_SLUG = "apple_health"
_APPLE_HEALTH_PROVIDER_NAME = "Apple Health"


def _coalesce_latest_sample(
    existing: AppleHealthStepDayIn,
    candidate: AppleHealthStepDayIn,
) -> AppleHealthStepDayIn:
    """Pick one sample when the client sends duplicate dates in the same batch.

    Prefer the one with the latest end_at, otherwise the later start_at, otherwise
    the later item (candidate).
    """
    existing_key = (
        existing.end_at or existing.start_at or datetime.min.replace(tzinfo=UTC)
    )
    candidate_key = (
        candidate.end_at or candidate.start_at or datetime.min.replace(tzinfo=UTC)
    )
    return candidate if candidate_key >= existing_key else existing


async def _upsert_apple_health_connection(
    *,
    db: AsyncSession,
    patient_id: int,
    source_count: int,
    last_synced_at: datetime | None,
    status_value: str = "connected",
    last_error: str | None = None,
) -> PatientDataConnection:
    stmt = insert(PatientDataConnection).values(
        patient_id=patient_id,
        provider_name=_APPLE_HEALTH_PROVIDER_NAME,
        provider_slug=_APPLE_HEALTH_PROVIDER_SLUG,
        status=status_value,
        source_count=max(int(source_count), 0),
        last_error=last_error,
        last_synced_at=last_synced_at,
        is_active=True,
    )
    await db.execute(
        stmt.on_conflict_do_update(
            constraint="uq_patient_data_connections_patient_provider",
            set_={
                "provider_name": stmt.excluded.provider_name,
                "status": stmt.excluded.status,
                "source_count": stmt.excluded.source_count,
                "last_error": stmt.excluded.last_error,
                "last_synced_at": stmt.excluded.last_synced_at,
                "is_active": True,
                "updated_at": func.now(),
            },
        )
    )
    result = await db.execute(
        select(PatientDataConnection).where(
            PatientDataConnection.patient_id == patient_id,
            PatientDataConnection.provider_slug == _APPLE_HEALTH_PROVIDER_SLUG,
        )
    )
    connection = result.scalar_one()
    return connection


def _sync_event_details(
    *,
    payload: AppleHealthStepsSyncRequest,
    inserted_days: int,
    updated_days: int,
    unchanged_days: int,
) -> str:
    parts = [
        f"received_samples={len(payload.samples)}",
        f"inserted_days={inserted_days}",
        f"updated_days={updated_days}",
        f"unchanged_days={unchanged_days}",
    ]
    if payload.device_name:
        parts.append(f"device={payload.device_name}")
    if payload.app_version:
        parts.append(f"app_version={payload.app_version}")
    if payload.client_anchor:
        parts.append("client_anchor_present=true")
    return "; ".join(parts)


@router.post(
    "/patient/{patient_id}/steps/sync",
    response_model=AppleHealthStepsSyncResponse,
)
async def sync_apple_health_steps(
    patient_id: int,
    payload: AppleHealthStepsSyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest Apple Health daily step totals from an iOS client.

    MVP scope:
    - Daily aggregate step totals only
    - Idempotent upsert by (patient_id, sample_date)
    - Owner-only sync (clinicians can read trends but should not push patient device data)
    """
    patient = await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="apple_health",
    )
    if patient.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the patient owner can sync Apple Health data",
        )

    deduped_by_date: dict[date, AppleHealthStepDayIn] = {}
    for sample in payload.samples:
        existing = deduped_by_date.get(sample.sample_date)
        deduped_by_date[sample.sample_date] = (
            _coalesce_latest_sample(existing, sample) if existing else sample
        )

    unique_samples = [deduped_by_date[d] for d in sorted(deduped_by_date)]
    unique_dates = [sample.sample_date for sample in unique_samples]

    existing_rows_by_date: dict[date, PatientAppleHealthStepDaily] = {}
    if unique_dates:
        rows = await db.execute(
            select(PatientAppleHealthStepDaily).where(
                PatientAppleHealthStepDaily.patient_id == patient_id,
                PatientAppleHealthStepDaily.sample_date.in_(unique_dates),
            )
        )
        existing_rows_by_date = {
            row.sample_date: row for row in rows.scalars().all()
        }

    inserted_days = 0
    updated_days = 0
    unchanged_days = 0
    latest_sample_date: date | None = None

    payload_rows: list[dict] = []
    note = None
    if payload.device_name or payload.app_version:
        note_parts = []
        if payload.device_name:
            note_parts.append(f"device={payload.device_name}")
        if payload.app_version:
            note_parts.append(f"app_version={payload.app_version}")
        note = "; ".join(note_parts)

    for sample in unique_samples:
        latest_sample_date = sample.sample_date
        current = existing_rows_by_date.get(sample.sample_date)
        if current is None:
            inserted_days += 1
        else:
            changed = any(
                [
                    int(current.step_count) != int(sample.step_count),
                    current.start_at != sample.start_at,
                    current.end_at != sample.end_at,
                    (current.timezone or "") != (sample.timezone or ""),
                    (current.source_name or "") != (sample.source_name or ""),
                    (current.source_bundle_id or "") != (sample.source_bundle_id or ""),
                    (current.source_uuid or "") != (sample.source_uuid or ""),
                    (current.sync_anchor or "") != (payload.client_anchor or ""),
                ]
            )
            if changed:
                updated_days += 1
            else:
                unchanged_days += 1

        payload_rows.append(
            {
                "patient_id": patient_id,
                "sample_date": sample.sample_date,
                "step_count": int(sample.step_count),
                "start_at": sample.start_at,
                "end_at": sample.end_at,
                "timezone": sample.timezone,
                "source_name": sample.source_name or _APPLE_HEALTH_PROVIDER_NAME,
                "source_bundle_id": sample.source_bundle_id,
                "source_uuid": sample.source_uuid,
                "sync_anchor": payload.client_anchor,
                "ingest_note": note,
            }
        )

    if payload_rows:
        stmt = insert(PatientAppleHealthStepDaily).values(payload_rows)
        await db.execute(
            stmt.on_conflict_do_update(
                constraint="uq_patient_apple_steps_patient_date",
                set_={
                    "step_count": stmt.excluded.step_count,
                    "start_at": stmt.excluded.start_at,
                    "end_at": stmt.excluded.end_at,
                    "timezone": stmt.excluded.timezone,
                    "source_name": stmt.excluded.source_name,
                    "source_bundle_id": stmt.excluded.source_bundle_id,
                    "source_uuid": stmt.excluded.source_uuid,
                    "sync_anchor": stmt.excluded.sync_anchor,
                    "ingest_note": stmt.excluded.ingest_note,
                    "updated_at": func.now(),
                },
            )
        )

    total_synced_days = int(
        (
            await db.scalar(
                select(func.count(PatientAppleHealthStepDaily.id)).where(
                    PatientAppleHealthStepDaily.patient_id == patient_id
                )
            )
        )
        or 0
    )
    last_synced_at = payload.sync_completed_at or datetime.now(UTC)
    connection = await _upsert_apple_health_connection(
        db=db,
        patient_id=patient_id,
        source_count=total_synced_days,
        last_synced_at=last_synced_at,
    )
    db.add(
        PatientConnectionSyncEvent(
            patient_id=patient_id,
            connection_id=connection.id,
            provider_slug=_APPLE_HEALTH_PROVIDER_SLUG,
            event_type="sync_completed",
            status_before=connection.status,
            status_after="connected",
            details=_sync_event_details(
                payload=payload,
                inserted_days=inserted_days,
                updated_days=updated_days,
                unchanged_days=unchanged_days,
            ),
            triggered_by_user_id=current_user.id,
        )
    )

    await db.commit()

    logger.info(
        "Apple Health steps sync patient=%s received=%s unique=%s inserted=%s updated=%s unchanged=%s",
        patient_id,
        len(payload.samples),
        len(unique_samples),
        inserted_days,
        updated_days,
        unchanged_days,
    )

    return AppleHealthStepsSyncResponse(
        patient_id=patient_id,
        received_samples=len(payload.samples),
        unique_days_received=len(unique_samples),
        inserted_days=inserted_days,
        updated_days=updated_days,
        unchanged_days=unchanged_days,
        latest_sample_date=latest_sample_date,
        last_synced_at=last_synced_at,
        connection_status="connected",
        client_anchor=payload.client_anchor,
    )


@router.get(
    "/patient/{patient_id}/steps",
    response_model=AppleHealthStepsTrendResponse,
)
async def get_apple_health_steps_trend(
    patient_id: int,
    days: int = Query(default=30, ge=1, le=3650),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Return Apple Health steps trend data for a patient."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="apple_health",
    )

    if start_date and end_date and end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be greater than or equal to start_date",
        )
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=days - 1)

    rows = await db.execute(
        select(PatientAppleHealthStepDaily)
        .where(
            PatientAppleHealthStepDaily.patient_id == patient_id,
            PatientAppleHealthStepDaily.sample_date >= start_date,
            PatientAppleHealthStepDaily.sample_date <= end_date,
        )
        .order_by(PatientAppleHealthStepDaily.sample_date.asc())
    )
    samples = list(rows.scalars().all())
    points = [
        AppleHealthStepTrendPoint(
            sample_date=row.sample_date,
            step_count=int(row.step_count),
            start_at=row.start_at,
            end_at=row.end_at,
            timezone=row.timezone,
            source_name=row.source_name,
        )
        for row in samples
    ]
    total_steps = sum(point.step_count for point in points)
    average_steps = (total_steps / len(points)) if points else None

    connection_row = await db.execute(
        select(PatientDataConnection).where(
            PatientDataConnection.patient_id == patient_id,
            PatientDataConnection.provider_slug == _APPLE_HEALTH_PROVIDER_SLUG,
        )
    )
    connection = connection_row.scalar_one_or_none()

    latest_step_count = points[-1].step_count if points else None
    latest_sample_date = points[-1].sample_date if points else None

    return AppleHealthStepsTrendResponse(
        patient_id=patient_id,
        start_date=start_date,
        end_date=end_date,
        points=points,
        total_steps=total_steps,
        average_steps=round(average_steps, 2) if average_steps is not None else None,
        latest_step_count=latest_step_count,
        latest_sample_date=latest_sample_date,
        last_synced_at=connection.last_synced_at if connection else None,
    )


@router.get(
    "/patient/{patient_id}/status",
    response_model=AppleHealthSyncStatusResponse,
)
async def get_apple_health_sync_status(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Return Apple Health connection + sync coverage status."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="apple_health",
    )

    connection_result = await db.execute(
        select(PatientDataConnection).where(
            PatientDataConnection.patient_id == patient_id,
            PatientDataConnection.provider_slug == _APPLE_HEALTH_PROVIDER_SLUG,
        )
    )
    connection = connection_result.scalar_one_or_none()

    aggregates = await db.execute(
        select(
            func.count(PatientAppleHealthStepDaily.id),
            func.min(PatientAppleHealthStepDaily.sample_date),
            func.max(PatientAppleHealthStepDaily.sample_date),
        ).where(PatientAppleHealthStepDaily.patient_id == patient_id)
    )
    total_synced_days, earliest_sample_date, latest_sample_date = aggregates.one()

    if not connection:
        return AppleHealthSyncStatusResponse(
            patient_id=patient_id,
            status="disconnected",
            is_active=False,
            total_synced_days=int(total_synced_days or 0),
            earliest_sample_date=earliest_sample_date,
            latest_sample_date=latest_sample_date,
        )

    return AppleHealthSyncStatusResponse(
        patient_id=patient_id,
        status=connection.status,
        is_active=bool(connection.is_active),
        last_synced_at=connection.last_synced_at,
        last_error=connection.last_error,
        total_synced_days=int(total_synced_days or 0),
        earliest_sample_date=earliest_sample_date,
        latest_sample_date=latest_sample_date,
    )
