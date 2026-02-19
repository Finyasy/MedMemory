from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import app.services.provider_sync as provider_sync
from app.models import PatientDataConnection
from app.services.provider_sync import (
    LiveFHIRSyncAdapter,
    LiveProviderConfig,
    LocalDeltaScanAdapter,
    ProviderSyncResult,
    _map_encounter_to_payload,
    _map_medication_request_to_payload,
    _map_observation_to_lab_payload,
    _provider_tokens,
    get_provider_sync_adapter,
    validate_provider_sync_connection,
)


def test_provider_tokens_include_slug_and_name_terms():
    tokens = _provider_tokens(
        "kenya_health_information_system_khis",
        "Kenya Health Information System (KHIS)",
    )
    assert "kenya_health_information_system_khis" in tokens
    assert "kenya" in tokens
    assert "khis" in tokens


def test_get_provider_sync_adapter_uses_default_for_unknown_slug():
    adapter = get_provider_sync_adapter("custom_unknown_provider")
    assert isinstance(adapter, LocalDeltaScanAdapter)


def test_get_provider_sync_adapter_uses_live_adapter_for_kenya_sources():
    adapter = get_provider_sync_adapter("kenya_health_information_system_khis")
    assert isinstance(adapter, LiveFHIRSyncAdapter)


def test_map_observation_to_lab_payload():
    connection = PatientDataConnection(
        patient_id=123,
        provider_name="KHIS",
        provider_slug="kenya_health_information_system_khis",
    )
    resource = {
        "id": "obs-1",
        "status": "final",
        "code": {
            "coding": [{"code": "4548-4", "display": "Hemoglobin A1c"}],
            "text": "HbA1c",
        },
        "valueQuantity": {"value": 6.1, "unit": "%"},
        "effectiveDateTime": "2026-02-17T10:00:00Z",
        "issued": "2026-02-17T10:05:00Z",
        "performer": [{"display": "Nairobi Lab"}],
    }

    payload = _map_observation_to_lab_payload(connection=connection, resource=resource)

    assert payload is not None
    assert payload["patient_id"] == 123
    assert payload["test_name"] in {"Hemoglobin A1c", "HbA1c"}
    assert payload["test_code"] == "4548-4"
    assert payload["numeric_value"] == 6.1
    assert payload["unit"] == "%"
    assert payload["source_id"] == "obs-1"
    assert payload["source_system"] == "kenya_health_information_system_khis"


def test_map_medication_request_to_payload():
    connection = PatientDataConnection(
        patient_id=55,
        provider_name="SHR",
        provider_slug="national_shr_afyayangu",
    )
    resource = {
        "id": "med-9",
        "status": "active",
        "medicationCodeableConcept": {
            "coding": [{"code": "860975", "display": "Metformin"}]
        },
        "authoredOn": "2026-02-10",
        "dosageInstruction": [
            {
                "text": "Take one tablet twice daily",
                "doseAndRate": [{"doseQuantity": {"value": 500, "unit": "mg"}}],
                "route": {"text": "oral"},
            }
        ],
        "requester": {"display": "Dr. Achieng"},
    }

    payload = _map_medication_request_to_payload(connection=connection, resource=resource)

    assert payload is not None
    assert payload["patient_id"] == 55
    assert payload["name"] == "Metformin"
    assert payload["drug_code"] == "860975"
    assert payload["dosage_value"] == 500.0
    assert payload["dosage_unit"] == "mg"
    assert payload["status"] == "active"
    assert payload["is_active"] is True
    assert payload["source_id"] == "med-9"
    assert payload["source_system"] == "national_shr_afyayangu"


def test_map_encounter_to_payload():
    connection = PatientDataConnection(
        patient_id=88,
        provider_name="DHA",
        provider_slug="digital_health_agency_dha",
    )
    resource = {
        "id": "enc-3",
        "status": "finished",
        "class": {"code": "AMB"},
        "period": {
            "start": "2026-02-01T08:00:00Z",
            "end": "2026-02-01T08:30:00Z",
        },
        "serviceProvider": {"display": "Mbagathi Hospital"},
        "participant": [{"individual": {"display": "Dr. Kamau"}}],
        "reasonCode": [{"text": "Hypertension follow-up"}],
    }

    payload = _map_encounter_to_payload(connection=connection, resource=resource)

    assert payload is not None
    assert payload["patient_id"] == 88
    assert payload["encounter_type"] == "outpatient"
    assert payload["status"] == "completed"
    assert payload["facility"] == "Mbagathi Hospital"
    assert payload["provider_name"] == "Dr. Kamau"
    assert payload["source_id"] == "enc-3"
    assert payload["source_system"] == "digital_health_agency_dha"


@pytest.mark.anyio
async def test_live_fhir_sync_uses_local_fallback_when_live_fetch_fails(monkeypatch):
    connection = PatientDataConnection(
        patient_id=99,
        provider_name="KHIS",
        provider_slug="kenya_health_information_system_khis",
    )
    config = LiveProviderConfig(
        provider_key="kenya_health_information_system_khis",
        base_url="https://khis-fhir.test",
        bearer_token=None,
        api_key=None,
        timeout_seconds=10,
        verify_ssl=True,
    )

    monkeypatch.setattr(
        provider_sync,
        "_resolve_live_provider_config",
        lambda _connection: config,
    )
    monkeypatch.setattr(
        provider_sync.settings,
        "provider_sync_live_fallback_to_local_scan",
        True,
    )

    async def _raise_patient_reference(**_kwargs):
        raise RuntimeError("live fetch failed")

    monkeypatch.setattr(
        provider_sync,
        "_resolve_patient_reference",
        _raise_patient_reference,
    )

    class _FallbackAdapter:
        async def sync(self, *, db, connection, now):
            return ProviderSyncResult(
                source_count_total=7,
                source_count_delta=2,
                details="delta=2 total=7",
            )

    adapter = LiveFHIRSyncAdapter(local_fallback_adapter=_FallbackAdapter())
    result = await adapter.sync(
        db=SimpleNamespace(),
        connection=connection,
        now=datetime.now(UTC),
    )

    assert result.source_count_total == 7
    assert result.source_count_delta == 2
    assert "live_fhir_with_local_fallback" in result.details
    assert "live fetch failed" in result.details


@pytest.mark.anyio
async def test_validate_provider_sync_connection_uses_local_fallback_on_live_failure(
    monkeypatch,
):
    connection = PatientDataConnection(
        patient_id=99,
        provider_name="KHIS",
        provider_slug="kenya_health_information_system_khis",
    )
    config = LiveProviderConfig(
        provider_key="kenya_health_information_system_khis",
        base_url="https://khis-fhir.test",
        bearer_token=None,
        api_key=None,
        timeout_seconds=10,
        verify_ssl=True,
    )

    monkeypatch.setattr(
        provider_sync,
        "_resolve_live_provider_config",
        lambda _connection: config,
    )
    monkeypatch.setattr(
        provider_sync.settings,
        "provider_sync_live_fallback_to_local_scan",
        True,
    )

    async def _fake_resolve_patient_reference(**_kwargs):
        return "Patient/abc-123"

    async def _raise_count(**_kwargs):
        raise RuntimeError("provider returned non-FHIR payload")

    monkeypatch.setattr(
        provider_sync,
        "_resolve_patient_reference",
        _fake_resolve_patient_reference,
    )
    monkeypatch.setattr(
        provider_sync,
        "_fetch_fhir_resource_count",
        _raise_count,
    )

    class _FallbackAdapter:
        async def sync(self, *, db, connection, now):
            return ProviderSyncResult(
                source_count_total=11,
                source_count_delta=3,
                details="delta=3 total=11",
            )

    monkeypatch.setattr(provider_sync, "_LOCAL_DELTA_ADAPTER", _FallbackAdapter())

    result = await validate_provider_sync_connection(
        db=SimpleNamespace(),
        connection=connection,
    )

    assert result.ok is True
    assert result.mode == "local_fallback"
    assert result.provider_key == "kenya_health_information_system_khis"
    assert result.base_url == "https://khis-fhir.test"
    assert "Falling back to local delta scan" in result.details
