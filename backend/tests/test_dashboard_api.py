from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.api import dashboard as dashboard_api
from app.models import (
    LabResult,
    PatientDataConnection,
    PatientMetricDailySummary,
    PatientWatchMetric,
    User,
)


class _FakeScalars:
    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return list(self._items)


class _FakeResult:
    def __init__(self, scalars=None, scalar=None, rows=None):
        self._scalars = list(scalars or [])
        self._scalar = scalar
        self._rows = list(rows or [])

    def scalars(self):
        return _FakeScalars(self._scalars)

    def scalar_one_or_none(self):
        return self._scalar

    def all(self):
        return list(self._rows)


class _FakeDB:
    def __init__(self, execute_results=None, scalar_results=None):
        self._execute_results = list(execute_results or [])
        self._scalar_results = list(scalar_results or [])
        self.added = []

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

    async def flush(self):
        return None

    async def refresh(self, _instance):
        return None

    async def delete(self, _instance):
        return None


def _fake_user() -> User:
    return User(
        id=1,
        email="tester@example.com",
        hashed_password="hashed",
        full_name="Test User",
        is_active=True,
    )


@pytest.mark.anyio
async def test_get_dashboard_highlights_uses_latest_per_metric(monkeypatch):
    async def _allow_access(**_kwargs):
        return SimpleNamespace(id=1, user_id=1)

    monkeypatch.setattr(dashboard_api, "get_authorized_patient", _allow_access)

    now = datetime.now(UTC)
    summary_date = now.date()
    summary_rows = [
        PatientMetricDailySummary(
            id=11,
            patient_id=1,
            summary_date=summary_date,
            metric_key="ldl_cholesterol",
            metric_name="LDL Cholesterol",
            value_text="144",
            numeric_value=144.0,
            unit="mg/dL",
            status="out_of_range",
            direction="above",
            trend_delta=-12.0,
            observed_at=now,
            source_type="lab_result",
            source_id=11,
            confidence_score=0.92,
            confidence_label="high",
            freshness_days=0,
            excluded_from_insights=False,
        ),
        PatientMetricDailySummary(
            id=12,
            patient_id=1,
            summary_date=summary_date,
            metric_key="vitamin_d",
            metric_name="Vitamin D",
            value_text="99",
            numeric_value=99.0,
            unit="ng/mL",
            status="in_range",
            direction="in_range",
            trend_delta=2.0,
            observed_at=now - timedelta(days=2),
            source_type="lab_result",
            source_id=12,
            confidence_score=0.88,
            confidence_label="high",
            freshness_days=2,
            excluded_from_insights=False,
        ),
    ]
    db = _FakeDB(
        execute_results=[
            _FakeResult(scalars=summary_rows),
            _FakeResult(scalars=[]),
            _FakeResult(rows=[(11, "70-100"), (12, "30-100")]),
        ],
        scalar_results=[now],
    )
    response = await dashboard_api.get_dashboard_highlights(
        patient_id=1,
        db=db,
        current_user=_fake_user(),
    )

    assert response.summary.out_of_range == 1
    assert response.summary.in_range == 1
    assert response.summary.tracked_metrics == 2
    assert len(response.highlights) == 2
    ldl = next(
        item for item in response.highlights if item.metric_key == "ldl_cholesterol"
    )
    assert ldl.trend_delta == pytest.approx(-12.0)
    assert ldl.direction == "above"


def test_parse_reference_range_parses_common_formats():
    assert dashboard_api.parse_reference_range("70-100 mg/dL") == (70.0, 100.0)
    assert dashboard_api.parse_reference_range("3.5 – 5.0") == (3.5, 5.0)
    assert dashboard_api.parse_reference_range("normal") == (None, None)


def test_normalize_metric_key_removes_symbols():
    assert dashboard_api.normalize_metric_key("HbA1C %") == "hba1c"
    assert dashboard_api.normalize_metric_key("LDL Cholesterol") == "ldl_cholesterol"


def test_watch_trigger_reason_for_bounds_and_abnormal():
    watch_above = PatientWatchMetric(
        patient_id=1,
        metric_key="ldl_cholesterol",
        metric_name="LDL Cholesterol",
        upper_bound=120.0,
        direction="above",
    )
    lab = LabResult(
        patient_id=1,
        test_name="LDL Cholesterol",
        value="144",
        numeric_value=144.0,
        is_abnormal=True,
    )
    triggered, reason, kind, _delta = dashboard_api._watch_trigger_reason(
        watch_above,
        lab,
        None,
    )
    assert triggered is True
    assert "above watch upper bound" in reason
    assert kind == "threshold"

    watch_auto = PatientWatchMetric(
        patient_id=1,
        metric_key="ldl_cholesterol",
        metric_name="LDL Cholesterol",
        direction="both",
    )
    triggered_auto, reason_auto, kind_auto, _delta_auto = (
        dashboard_api._watch_trigger_reason(
            watch_auto,
            lab,
            None,
        )
    )
    assert triggered_auto is True
    assert "flagged abnormal" in reason_auto
    assert kind_auto == "abnormal"


def test_watch_trigger_reason_for_sharp_trend_change():
    watch = PatientWatchMetric(
        patient_id=1,
        metric_key="hemoglobin_a1c",
        metric_name="Hemoglobin A1C",
        direction="both",
    )
    latest = LabResult(
        patient_id=1,
        test_name="Hemoglobin A1C",
        value="7.2",
        numeric_value=7.2,
        is_abnormal=False,
    )
    previous = LabResult(
        patient_id=1,
        test_name="Hemoglobin A1C",
        value="5.8",
        numeric_value=5.8,
        is_abnormal=False,
    )
    triggered, reason, kind, delta = dashboard_api._watch_trigger_reason(
        watch,
        latest,
        previous,
    )
    assert triggered is True
    assert "shifted up" in reason
    assert kind == "trend_change"
    assert delta == pytest.approx(1.4)


@pytest.mark.anyio
async def test_metric_detail_normalizes_provider_units_and_tracks_exclusions(monkeypatch):
    monkeypatch.setattr(dashboard_api.settings, "dashboard_metric_about_rag_enabled", False)

    async def _allow_access(**_kwargs):
        return SimpleNamespace(id=1, user_id=1)

    monkeypatch.setattr(dashboard_api, "get_authorized_patient", _allow_access)

    now = datetime.now(UTC)
    labs = [
        LabResult(
            id=31,
            patient_id=1,
            test_name="LDL-C",
            value="3.1",
            numeric_value=3.1,
            unit="mmol/L",
            reference_range="1.0-2.5",
            is_abnormal=True,
            collected_at=now,
            performing_lab="Provider A",
        ),
        LabResult(
            id=30,
            patient_id=1,
            test_name="LDL Cholesterol",
            value="120",
            numeric_value=120.0,
            unit="mg/dL",
            reference_range="70-100",
            is_abnormal=True,
            collected_at=now - timedelta(days=35),
            source_system="Provider B",
        ),
        LabResult(
            id=29,
            patient_id=1,
            test_name="LDL Cholesterol",
            value="130",
            numeric_value=130.0,
            unit=None,
            reference_range=None,
            is_abnormal=True,
            collected_at=None,
        ),
    ]
    db = _FakeDB(execute_results=[_FakeResult(scalars=labs)])
    response = await dashboard_api.get_metric_detail(
        patient_id=1,
        metric_key="ldl",
        db=db,
        current_user=_fake_user(),
    )

    assert response.metric_key == "ldl_cholesterol"
    assert response.normalized_unit == "mg/dL"
    assert response.normalization_applied is True
    assert response.latest_numeric_value == pytest.approx(119.877, rel=1e-3)
    assert response.excluded_points_count == 1
    assert any(point.raw_unit == "mmol/L" for point in response.trend)
    assert any(point.excluded_from_insights for point in response.trend)


@pytest.mark.anyio
async def test_dry_run_connection_sync_returns_validation_payload(monkeypatch):
    async def _allow_access(**_kwargs):
        return SimpleNamespace(id=1, user_id=1)

    monkeypatch.setattr(dashboard_api, "get_authorized_patient", _allow_access)

    async def _fake_validate_provider_sync_connection(*, db, connection):
        assert db is not None
        assert connection.id == 99
        return SimpleNamespace(
            ok=True,
            mode="live_fhir",
            provider_key="kenya_health_information_system_khis",
            base_url="https://example-khis-fhir.test",
            patient_ref="Patient/abc-123",
            counts={
                "Observation": 12,
                "MedicationRequest": 4,
                "Encounter": 7,
            },
            details="Live provider connectivity check passed.",
        )

    monkeypatch.setattr(
        dashboard_api,
        "validate_provider_sync_connection",
        _fake_validate_provider_sync_connection,
    )

    connection = PatientDataConnection(
        id=99,
        patient_id=1,
        provider_name="KHIS",
        provider_slug="kenya_health_information_system_khis",
        status="connected",
        source_count=0,
        is_active=True,
    )
    db = _FakeDB(execute_results=[_FakeResult(scalar=connection)])

    response = await dashboard_api.dry_run_connection_sync(
        patient_id=1,
        connection_id=99,
        db=db,
        current_user=_fake_user(),
    )

    assert response.ok is True
    assert response.mode == "live_fhir"
    assert response.provider_key == "kenya_health_information_system_khis"
    assert response.base_url == "https://example-khis-fhir.test"
    assert response.patient_ref == "Patient/abc-123"
    assert response.counts["Observation"] == 12
    assert "connectivity check passed" in response.details
    assert any(
        "Manual sync dry-run" in (getattr(item, "details", "") or "")
        for item in db.added
    )


@pytest.mark.anyio
async def test_upsert_data_connection_rejects_non_kenya_provider_slug(monkeypatch):
    async def _allow_access(**_kwargs):
        return SimpleNamespace(id=1, user_id=1)

    monkeypatch.setattr(dashboard_api, "get_authorized_patient", _allow_access)

    payload = dashboard_api.DataConnectionUpsert(
        provider_name="Kaiser Permanente",
        provider_slug="kaiser_permanente",
        status="connected",
        source_count=0,
        is_active=True,
    )
    db = _FakeDB()
    with pytest.raises(dashboard_api.HTTPException) as exc:
        await dashboard_api.upsert_data_connection(
            patient_id=1,
            payload=payload,
            db=db,
            current_user=_fake_user(),
        )

    assert exc.value.status_code == 422
    assert "Unsupported provider_slug" in str(exc.value.detail)


@pytest.mark.anyio
async def test_evaluate_metric_alerts_skips_low_confidence_latest():
    watch = PatientWatchMetric(
        id=7,
        patient_id=1,
        metric_key="ldl_cholesterol",
        metric_name="LDL Cholesterol",
        upper_bound=120.0,
        direction="above",
        is_active=True,
    )
    now = datetime.now(UTC)
    latest_low_conf = LabResult(
        id=41,
        patient_id=1,
        test_name="LDL Cholesterol",
        value="145",
        numeric_value=145.0,
        unit=None,
        reference_range=None,
        is_abnormal=True,
        collected_at=None,
    )
    previous = LabResult(
        id=40,
        patient_id=1,
        test_name="LDL Cholesterol",
        value="130",
        numeric_value=130.0,
        unit="mg/dL",
        reference_range="70-100",
        is_abnormal=True,
        collected_at=now - timedelta(days=45),
        performing_lab="Quest",
    )
    db = _FakeDB(
        execute_results=[
            _FakeResult(scalars=[watch]),
            _FakeResult(scalars=[latest_low_conf, previous]),
        ],
        scalar_results=[0],
    )

    result = await dashboard_api.evaluate_metric_alerts_for_patient(patient_id=1, db=db)

    assert result.generated == 0
    assert db.added == []
