from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import apple_health as apple_health_api
from app.models import (
    PatientAppleHealthStepDaily,
    PatientConnectionSyncEvent,
    PatientDataConnection,
    User,
)
from app.schemas.apple_health import AppleHealthStepDayIn, AppleHealthStepsSyncRequest


class _FakeScalars:
    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return list(self._items)


class _FakeResult:
    def __init__(self, *, scalars=None, scalar=None, rows=None):
        self._scalars = list(scalars or [])
        self._scalar = scalar
        self._rows = list(rows or [])

    def scalars(self):
        return _FakeScalars(self._scalars)

    def scalar_one(self):
        if self._scalar is None:
            raise AssertionError("Expected scalar result")
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def one(self):
        if not self._rows:
            raise AssertionError("Expected aggregate row")
        return self._rows[0]


class _FakeDB:
    def __init__(self, *, execute_results=None, scalar_results=None):
        self._execute_results = list(execute_results or [])
        self._scalar_results = list(scalar_results or [])
        self.added: list[object] = []
        self.committed = False

    async def execute(self, *_args, **_kwargs):
        if not self._execute_results:
            return _FakeResult()
        return self._execute_results.pop(0)

    async def scalar(self, *_args, **_kwargs):
        if not self._scalar_results:
            return None
        return self._scalar_results.pop(0)

    def add(self, instance):
        self.added.append(instance)

    async def commit(self):
        self.committed = True


def _fake_user() -> User:
    return User(
        id=1,
        email="owner@example.com",
        hashed_password="hashed",
        full_name="Owner",
        is_active=True,
    )


def test_coalesce_latest_sample_prefers_latest_interval():
    earlier = AppleHealthStepDayIn(
        sample_date=date(2026, 3, 10),
        step_count=1000,
        start_at=datetime(2026, 3, 10, 0, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 10, 18, 0, tzinfo=UTC),
    )
    later = AppleHealthStepDayIn(
        sample_date=date(2026, 3, 10),
        step_count=1800,
        start_at=datetime(2026, 3, 10, 0, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 10, 22, 0, tzinfo=UTC),
    )

    chosen = apple_health_api._coalesce_latest_sample(earlier, later)

    assert chosen is later


def test_sync_event_details_includes_optional_device_metadata():
    payload = AppleHealthStepsSyncRequest(
        samples=[],
        client_anchor="anchor-1",
        device_name="iPhone",
        app_version="1.2.3",
    )

    details = apple_health_api._sync_event_details(
        payload=payload,
        inserted_days=2,
        updated_days=1,
        unchanged_days=0,
    )

    assert "received_samples=0" in details
    assert "inserted_days=2" in details
    assert "updated_days=1" in details
    assert "device=iPhone" in details
    assert "app_version=1.2.3" in details
    assert "client_anchor_present=true" in details


@pytest.mark.anyio
async def test_sync_apple_health_steps_deduplicates_and_records_sync_event(monkeypatch):
    async def _allow_access(**_kwargs):
        return SimpleNamespace(id=10, user_id=1)

    monkeypatch.setattr(apple_health_api, "get_authorized_patient", _allow_access)

    existing_row = PatientAppleHealthStepDaily(
        patient_id=10,
        sample_date=date(2026, 3, 10),
        step_count=1200,
        start_at=datetime(2026, 3, 10, 0, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 10, 18, 0, tzinfo=UTC),
        timezone="UTC",
        source_name="Apple Health",
    )
    connection = PatientDataConnection(
        id=41,
        patient_id=10,
        provider_name="Apple Health",
        provider_slug="apple_health",
        status="connected",
        source_count=7,
        is_active=True,
        last_synced_at=datetime(2026, 3, 11, 8, 30, tzinfo=UTC),
    )
    db = _FakeDB(
        execute_results=[
            _FakeResult(scalars=[existing_row]),
            _FakeResult(),
            _FakeResult(),
            _FakeResult(scalar=connection),
        ],
        scalar_results=[7],
    )
    payload = AppleHealthStepsSyncRequest(
        samples=[
            AppleHealthStepDayIn(
                sample_date=date(2026, 3, 10),
                step_count=1200,
                start_at=datetime(2026, 3, 10, 0, 0, tzinfo=UTC),
                end_at=datetime(2026, 3, 10, 18, 0, tzinfo=UTC),
                timezone="UTC",
            ),
            AppleHealthStepDayIn(
                sample_date=date(2026, 3, 10),
                step_count=2400,
                start_at=datetime(2026, 3, 10, 0, 0, tzinfo=UTC),
                end_at=datetime(2026, 3, 10, 23, 0, tzinfo=UTC),
                timezone="UTC",
            ),
            AppleHealthStepDayIn(
                sample_date=date(2026, 3, 11),
                step_count=3000,
                start_at=datetime(2026, 3, 11, 0, 0, tzinfo=UTC),
                end_at=datetime(2026, 3, 11, 23, 0, tzinfo=UTC),
                timezone="UTC",
            ),
        ],
        client_anchor="anchor-2",
        sync_completed_at=datetime(2026, 3, 11, 8, 30, tzinfo=UTC),
        device_name="iPhone",
    )

    response = await apple_health_api.sync_apple_health_steps(
        patient_id=10,
        payload=payload,
        db=db,
        current_user=_fake_user(),
    )

    assert response.received_samples == 3
    assert response.unique_days_received == 2
    assert response.inserted_days == 1
    assert response.updated_days == 1
    assert response.unchanged_days == 0
    assert response.latest_sample_date == date(2026, 3, 11)
    assert response.client_anchor == "anchor-2"
    assert db.committed is True
    assert len(db.added) == 1
    event = db.added[0]
    assert isinstance(event, PatientConnectionSyncEvent)
    assert event.connection_id == 41
    assert "inserted_days=1" in (event.details or "")
    assert "updated_days=1" in (event.details or "")


@pytest.mark.anyio
async def test_sync_apple_health_steps_rejects_non_owner(monkeypatch):
    async def _allow_access(**_kwargs):
        return SimpleNamespace(id=10, user_id=99)

    monkeypatch.setattr(apple_health_api, "get_authorized_patient", _allow_access)

    with pytest.raises(HTTPException) as exc:
        await apple_health_api.sync_apple_health_steps(
            patient_id=10,
            payload=AppleHealthStepsSyncRequest(samples=[]),
            db=_FakeDB(),
            current_user=_fake_user(),
        )

    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_get_apple_health_steps_trend_calculates_rollup(monkeypatch):
    async def _allow_access(**_kwargs):
        return SimpleNamespace(id=10, user_id=1)

    monkeypatch.setattr(apple_health_api, "get_authorized_patient", _allow_access)

    rows = [
        PatientAppleHealthStepDaily(
            patient_id=10,
            sample_date=date(2026, 3, 8),
            step_count=1500,
            start_at=datetime(2026, 3, 8, 0, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 8, 23, 59, tzinfo=UTC),
            timezone="UTC",
            source_name="Apple Health",
        ),
        PatientAppleHealthStepDaily(
            patient_id=10,
            sample_date=date(2026, 3, 9),
            step_count=2500,
            start_at=datetime(2026, 3, 9, 0, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 9, 23, 59, tzinfo=UTC),
            timezone="UTC",
            source_name="Apple Health",
        ),
    ]
    connection = PatientDataConnection(
        id=41,
        patient_id=10,
        provider_name="Apple Health",
        provider_slug="apple_health",
        status="connected",
        source_count=2,
        is_active=True,
        last_synced_at=datetime(2026, 3, 9, 20, 0, tzinfo=UTC),
    )
    db = _FakeDB(
        execute_results=[
            _FakeResult(scalars=rows),
            _FakeResult(scalar=connection),
        ]
    )

    response = await apple_health_api.get_apple_health_steps_trend(
        patient_id=10,
        days=7,
        start_date=date(2026, 3, 8),
        end_date=date(2026, 3, 9),
        db=db,
        current_user=_fake_user(),
    )

    assert response.total_steps == 4000
    assert response.average_steps == 2000.0
    assert response.latest_step_count == 2500
    assert response.latest_sample_date == date(2026, 3, 9)
    assert response.last_synced_at == datetime(2026, 3, 9, 20, 0, tzinfo=UTC)


@pytest.mark.anyio
async def test_get_apple_health_sync_status_returns_disconnected_without_connection(monkeypatch):
    async def _allow_access(**_kwargs):
        return SimpleNamespace(id=10, user_id=1)

    monkeypatch.setattr(apple_health_api, "get_authorized_patient", _allow_access)

    db = _FakeDB(
        execute_results=[
            _FakeResult(scalar=None),
            _FakeResult(rows=[(5, date(2026, 3, 1), date(2026, 3, 10))]),
        ]
    )

    response = await apple_health_api.get_apple_health_sync_status(
        patient_id=10,
        db=db,
        current_user=_fake_user(),
    )

    assert response.status == "disconnected"
    assert response.is_active is False
    assert response.total_synced_days == 5
    assert response.earliest_sample_date == date(2026, 3, 1)
    assert response.latest_sample_date == date(2026, 3, 10)
