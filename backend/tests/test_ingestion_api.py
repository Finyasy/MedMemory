from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import ingestion as ingestion_api
from app.models import User
from app.schemas.ingestion import (
    BatchIngestionRequest,
    LabResultIngest,
    MedicationIngest,
)


class FakeResultAll:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeScalarResult:
    def __init__(self, scalar):
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar


class FakeDB:
    def __init__(self, results=None):
        self._results = list(results or [])

    async def execute(self, *_args, **_kwargs):
        if not self._results:
            return FakeResultAll([])
        return self._results.pop(0)


def _fake_user():
    return User(
        id=1,
        email="user@example.com",
        hashed_password="hashed",
        full_name="User",
        is_active=True,
    )


class FakeIngestionResult:
    def __init__(self, created=0, errors=None):
        self.created = created
        self.errors = errors or []
        self.timestamp = datetime.now(UTC)

    def to_dict(self):
        return {
            "success": len(self.errors) == 0,
            "records_created": self.created,
            "records_updated": 0,
            "records_skipped": 0,
            "errors": list(self.errors),
            "timestamp": self.timestamp,
        }


@pytest.mark.anyio
async def test_lab_batch_denies_unowned_patient():
    db = FakeDB(results=[FakeResultAll([(1,)])])
    payload = [
        LabResultIngest(patient_id=1, test_name="CBC"),
        LabResultIngest(patient_id=2, test_name="BMP"),
    ]

    with pytest.raises(HTTPException) as exc:
        await ingestion_api.ingest_lab_results_batch(
            payload, db=db, current_user=_fake_user()
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_batch_ingestion_aggregates_results(monkeypatch):
    db = FakeDB(results=[FakeResultAll([(1,)]), FakeResultAll([(1,)])])

    class FakeLabService:
        def __init__(self, *_args, **_kwargs):
            pass

        async def ingest_batch(self, *_args, **_kwargs):
            return FakeIngestionResult(created=2)

    class FakeMedicationService:
        def __init__(self, *_args, **_kwargs):
            pass

        async def ingest_batch(self, *_args, **_kwargs):
            return FakeIngestionResult(created=1, errors=["bad med"])

    monkeypatch.setattr(ingestion_api, "LabIngestionService", FakeLabService)
    monkeypatch.setattr(
        ingestion_api, "MedicationIngestionService", FakeMedicationService
    )

    request = BatchIngestionRequest(
        labs=[LabResultIngest(patient_id=1, test_name="CBC")],
        medications=[MedicationIngest(patient_id=1, name="Aspirin")],
    )

    response = await ingestion_api.ingest_batch(
        request, db=db, current_user=_fake_user()
    )

    assert response["total_records_created"] == 3
    assert response["total_errors"] == 1
    assert response["success"] is False
    assert response["details"]["labs"]["records_created"] == 2


@pytest.mark.anyio
async def test_discontinue_medication_denies_other_user(monkeypatch):
    medication = SimpleNamespace(id=50, patient_id=999)
    db = FakeDB(results=[FakeScalarResult(medication)])

    async def _deny_patient(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Patient not found")

    monkeypatch.setattr(ingestion_api, "get_patient_for_user", _deny_patient)

    with pytest.raises(HTTPException) as exc:
        await ingestion_api.discontinue_medication(
            medication_id=50,
            reason="done",
            db=db,
            current_user=_fake_user(),
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_ingest_lab_result_runs_auto_alert_evaluation(monkeypatch):
    async def _allow_patient(*_args, **_kwargs):
        return SimpleNamespace(id=1, user_id=1)

    class FakeLabService:
        def __init__(self, *_args, **_kwargs):
            pass

        async def ingest_single(self, data):
            return SimpleNamespace(
                id=999,
                patient_id=data["patient_id"],
                test_name=data["test_name"],
                test_code=None,
                category=None,
                value="140",
                numeric_value=140.0,
                unit="mg/dL",
                reference_range="70-100",
                status="abnormal",
                is_abnormal=True,
                collected_at=datetime.now(UTC),
                resulted_at=None,
                created_at=datetime.now(UTC),
            )

    called_patient_ids: list[set[int]] = []

    async def _capture_post_ingest(*, patient_ids, db):
        called_patient_ids.append(set(patient_ids))

    monkeypatch.setattr(ingestion_api, "get_patient_for_user", _allow_patient)
    monkeypatch.setattr(ingestion_api, "LabIngestionService", FakeLabService)
    monkeypatch.setattr(
        ingestion_api,
        "_post_lab_ingestion_automation",
        _capture_post_ingest,
    )

    payload = LabResultIngest(patient_id=1, test_name="LDL Cholesterol", numeric_value=140)
    response = await ingestion_api.ingest_lab_result(
        payload,
        db=FakeDB(),
        current_user=_fake_user(),
    )

    assert response.patient_id == 1
    assert called_patient_ids == [{1}]
