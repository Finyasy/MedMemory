from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.api import clinician as clinician_api
from app.schemas.clinician import (
    ClinicianAgentCitation,
    ClinicianAgentRunCreate,
    ClinicianAgentRunResponse,
    ClinicianAgentRunSummaryResponse,
)
from app.services.clinician_copilot import (
    TEMPLATE_DEFINITIONS,
    ClinicianCopilotService,
    _AbnormalLabItem,
    _AbnormalLabsOutput,
    _ConnectionEventItem,
    _ProviderSyncHealthOutput,
    _RecentDocumentsOutput,
)


def test_template_definitions_match_bounded_sequences():
    assert TEMPLATE_DEFINITIONS["chart_review"] == [
        ("patient_snapshot", "Patient snapshot"),
        ("recent_documents", "Recent documents"),
        ("abnormal_labs", "Abnormal labs"),
        ("draft_clinician_note_outline", "Draft clinician note outline"),
    ]
    assert TEMPLATE_DEFINITIONS["data_quality"][0][0] == "provider_sync_health"
    assert all(len(sequence) >= 3 for sequence in TEMPLATE_DEFINITIONS.values())


def test_compose_final_answer_uses_not_in_documents_when_docs_missing():
    service = ClinicianCopilotService(db=SimpleNamespace())
    answer = service._compose_final_answer(
        template="chart_review",
        prompt="review chart",
        outputs={
            "recent_documents": _RecentDocumentsOutput(total_documents=0, items=[]),
            "abnormal_labs": _AbnormalLabsOutput(total_abnormal=0, items=[]),
        },
    )
    assert "Not in documents." in answer


def test_build_suggestions_surfaces_lab_and_sync_attention():
    service = ClinicianCopilotService(db=SimpleNamespace())
    suggestions = service._build_suggestions(
        patient_id=44,
        outputs={
            "abnormal_labs": _AbnormalLabsOutput(
                total_abnormal=1,
                items=[
                    _AbnormalLabItem(
                        lab_result_id=10,
                        test_name="LDL Cholesterol",
                        value_text="180 mg/dL",
                    )
                ],
            ),
            "provider_sync_health": _ProviderSyncHealthOutput(
                connections=[],
                recent_failures=[
                    _ConnectionEventItem(
                        event_id=8,
                        provider_slug="kenya_health_information_system_khis",
                        event_type="sync_failed",
                        created_at=datetime.now(UTC),
                        last_error="timeout",
                    )
                ],
            ),
        },
    )

    kinds = [item.kind for item in suggestions]
    assert "review_abnormal_labs" in kinds
    assert "review_data_quality" in kinds


@pytest.mark.anyio
async def test_create_clinician_agent_run_endpoint_returns_service_payload(monkeypatch):
    audit_calls: list[dict[str, object]] = []
    metric_calls: list[tuple[str, str]] = []

    async def _record_access_audit(_db, **kwargs):
        audit_calls.append(kwargs)

    async def _allow_access(**_kwargs):
        return SimpleNamespace(id=5, user_id=5)

    monkeypatch.setattr(clinician_api, "get_authorized_patient", _allow_access)
    monkeypatch.setattr(clinician_api, "record_access_audit", _record_access_audit)
    monkeypatch.setattr(
        clinician_api,
        "ObservabilityRegistry",
        SimpleNamespace(
            get_instance=lambda: SimpleNamespace(
                record_copilot_run=lambda *, template, status: metric_calls.append((template, status))
            )
        ),
    )

    expected = ClinicianAgentRunResponse(
        id=1,
        patient_id=5,
        clinician_user_id=9,
        template="chart_review",
        prompt="summarize chart",
        status="completed",
        final_answer="Chart review complete.",
        citations=[
            ClinicianAgentCitation(
                source_type="document",
                source_id=3,
                label="Discharge note",
            )
        ],
        steps=[],
        suggestions=[],
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )

    class _FakeService:
        def __init__(self, db):
            assert db is not None

        async def create_run(self, **kwargs):
            assert kwargs["patient_id"] == 5
            assert kwargs["clinician_user_id"] == 9
            assert kwargs["template"] == "chart_review"
            return expected

    monkeypatch.setattr(clinician_api, "ClinicianCopilotService", _FakeService)

    response = await clinician_api.create_clinician_agent_run(
        data=ClinicianAgentRunCreate(
            patient_id=5,
            prompt="summarize chart",
            template="chart_review",
        ),
        db=SimpleNamespace(),
        current_user=SimpleNamespace(id=9, role="clinician"),
    )

    assert response == expected
    assert metric_calls == [("chart_review", "completed")]
    assert audit_calls == [
        {
            "actor_user_id": 9,
            "patient_id": 5,
            "action": "create_copilot_run",
            "metadata": {
                "run_id": 1,
                "template": "chart_review",
                "status": "completed",
            },
        }
    ]


@pytest.mark.anyio
async def test_get_clinician_agent_run_endpoint_maps_missing_to_404(monkeypatch):
    class _FakeService:
        def __init__(self, db):
            assert db is not None

        async def get_run_patient_id(self, run_id, *, clinician_user_id):
            assert run_id == 7
            assert clinician_user_id == 9
            raise ValueError("Clinician copilot run not found")

        async def get_run(self, run_id, *, clinician_user_id):
            assert run_id == 7
            assert clinician_user_id == 9
            raise ValueError("Clinician copilot run not found")

    monkeypatch.setattr(clinician_api, "ClinicianCopilotService", _FakeService)

    with pytest.raises(clinician_api.HTTPException) as exc:
        await clinician_api.get_clinician_agent_run(
            run_id=7,
            db=SimpleNamespace(),
            current_user=SimpleNamespace(id=9, role="clinician"),
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_get_clinician_agent_run_endpoint_rechecks_patient_access(monkeypatch):
    calls: list[tuple[int, int, str | None]] = []
    audit_calls: list[dict[str, object]] = []

    async def _record_access_audit(_db, **kwargs):
        audit_calls.append(kwargs)

    async def _allow_access(*, patient_id, db, current_user, scope=None):
        calls.append((patient_id, current_user.id, scope))
        return SimpleNamespace(id=patient_id, user_id=patient_id)

    monkeypatch.setattr(clinician_api, "get_authorized_patient", _allow_access)
    monkeypatch.setattr(clinician_api, "record_access_audit", _record_access_audit)

    expected = ClinicianAgentRunResponse(
        id=11,
        patient_id=5,
        clinician_user_id=9,
        template="chart_review",
        prompt="summarize chart",
        status="completed",
        final_answer="done",
        steps=[],
        suggestions=[],
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )

    class _FakeService:
        def __init__(self, db):
            assert db is not None

        async def get_run_patient_id(self, run_id, *, clinician_user_id):
            assert run_id == 11
            assert clinician_user_id == 9
            return 5

        async def get_run(self, run_id, *, clinician_user_id):
            assert run_id == 11
            assert clinician_user_id == 9
            return expected

    monkeypatch.setattr(clinician_api, "ClinicianCopilotService", _FakeService)

    response = await clinician_api.get_clinician_agent_run(
        run_id=11,
        db=SimpleNamespace(),
        current_user=SimpleNamespace(id=9, role="clinician"),
    )

    assert response == expected
    assert calls == [(5, 9, "chat")]
    assert audit_calls == [
        {
            "actor_user_id": 9,
            "patient_id": 5,
            "action": "view_copilot_run",
            "metadata": {
                "run_id": 11,
                "template": "chart_review",
                "status": "completed",
            },
        }
    ]


@pytest.mark.anyio
async def test_get_clinician_agent_run_endpoint_blocks_revoked_access(monkeypatch):
    async def _deny_access(**_kwargs):
        raise clinician_api.HTTPException(status_code=403, detail="Access not granted to this patient")

    monkeypatch.setattr(clinician_api, "get_authorized_patient", _deny_access)

    class _FakeService:
        def __init__(self, db):
            assert db is not None

        async def get_run_patient_id(self, run_id, *, clinician_user_id):
            assert run_id == 12
            assert clinician_user_id == 9
            return 5

        async def get_run(self, run_id, *, clinician_user_id):
            raise AssertionError("get_run should not be reached when access is denied")

    monkeypatch.setattr(clinician_api, "ClinicianCopilotService", _FakeService)

    with pytest.raises(clinician_api.HTTPException) as exc:
        await clinician_api.get_clinician_agent_run(
            run_id=12,
            db=SimpleNamespace(),
            current_user=SimpleNamespace(id=9, role="clinician"),
        )

    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_list_clinician_agent_runs_endpoint_returns_summaries(monkeypatch):
    audit_calls: list[dict[str, object]] = []

    async def _record_access_audit(_db, **kwargs):
        audit_calls.append(kwargs)

    async def _allow_access(**_kwargs):
        return SimpleNamespace(id=5, user_id=5)

    monkeypatch.setattr(clinician_api, "get_authorized_patient", _allow_access)
    monkeypatch.setattr(clinician_api, "record_access_audit", _record_access_audit)

    expected = [
        ClinicianAgentRunSummaryResponse(
            id=2,
            patient_id=5,
            clinician_user_id=9,
            template="data_quality",
            prompt="check sync quality",
            status="completed",
            final_answer_preview="Data quality review complete.",
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
    ]

    class _FakeService:
        def __init__(self, db):
            assert db is not None

        async def list_runs(self, **kwargs):
            assert kwargs["patient_id"] == 5
            assert kwargs["clinician_user_id"] == 9
            return expected

    monkeypatch.setattr(clinician_api, "ClinicianCopilotService", _FakeService)

    response = await clinician_api.list_clinician_agent_runs(
        patient_id=5,
        limit=10,
        db=SimpleNamespace(),
        current_user=SimpleNamespace(id=9, role="clinician"),
    )

    assert response == expected
    assert audit_calls == [
        {
            "actor_user_id": 9,
            "patient_id": 5,
            "action": "list_copilot_runs",
            "metadata": {
                "limit": 10,
                "returned_count": 1,
            },
        }
    ]
