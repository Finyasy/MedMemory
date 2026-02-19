from datetime import datetime

import pytest

from app.services.ingestion.base import IngestionResult, IngestionService
from app.services.ingestion.encounters import EncounterIngestionService
from app.services.ingestion.labs import LabIngestionService
from app.services.ingestion.medications import MedicationIngestionService


class DummyIngestionService(IngestionService[dict]):
    async def ingest_single(self, data: dict) -> dict:
        if data.get("fail"):
            raise ValueError("bad record")
        return data


def test_ingestion_result_to_dict():
    result = IngestionResult(success=True, records_created=2)
    data = result.to_dict()

    assert data["success"] is True
    assert data["records_created"] == 2
    assert "timestamp" in data


@pytest.mark.anyio
async def test_ingestion_batch_counts_errors():
    service = DummyIngestionService(db=None)
    result = await service.ingest_batch(
        [
            {"id": 1},
            {"id": 2, "fail": True},
        ]
    )

    assert result.records_created == 1
    assert result.records_skipped == 1
    assert result.success is False
    assert result.errors


def test_ingestion_helpers_parse_and_normalize():
    service = DummyIngestionService(db=None)

    assert service.parse_float("1,234.5") == 1234.5
    assert service.parse_float("invalid") is None
    assert service.parse_datetime("2024-01-02") == datetime(2024, 1, 2)
    assert service.normalize_status("Abnormal", ["normal", "abnormal"]) == "abnormal"


def test_lab_helpers_category_and_abnormal():
    service = LabIngestionService(db=None)

    assert service._detect_category("CBC Panel") == "Hematology"
    assert service._check_abnormal(
        status=None, numeric_value=15.0, reference_range="1-10"
    )
    assert service._check_abnormal(
        status="critical", numeric_value=None, reference_range=None
    )


def test_medication_helpers_parsing():
    service = MedicationIngestionService(db=None)

    value, unit = service._parse_dosage("10mg", None, None)
    assert value == 10.0
    assert unit == "mg"
    assert service._normalize_route("po") == "oral"
    assert service._parse_date("2024-01-02") is not None


def test_encounter_helpers_normalization_and_notes():
    service = EncounterIngestionService(db=None)

    assert service._normalize_encounter_type("ER") == "emergency"
    notes = service._build_clinical_notes(
        {
            "chief_complaint": "Headache",
            "assessment": "Migraine",
            "plan": "Rest",
        }
    )
    assert "Chief Complaint" in notes
    assert "Assessment" in notes
