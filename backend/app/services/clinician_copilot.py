"""Bounded clinician copilot orchestration for evidence-grounded chart review."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ClinicianAgentRun,
    ClinicianAgentStep,
    ClinicianAgentSuggestion,
    Document,
    LabResult,
    Medication,
    Patient,
    PatientConnectionSyncEvent,
    PatientDataConnection,
    Record,
)
from app.schemas.clinician import (
    ClinicianAgentCitation,
    ClinicianAgentRunResponse,
    ClinicianAgentRunSummaryResponse,
    ClinicianAgentStepResponse,
    ClinicianAgentSuggestionResponse,
)

STOPWORDS = {
    "about",
    "after",
    "chart",
    "from",
    "into",
    "latest",
    "need",
    "next",
    "patient",
    "please",
    "records",
    "review",
    "show",
    "summary",
    "that",
    "their",
    "this",
    "with",
}

TEMPLATE_DEFINITIONS: dict[str, list[tuple[str, str]]] = {
    "chart_review": [
        ("patient_snapshot", "Patient snapshot"),
        ("recent_documents", "Recent documents"),
        ("abnormal_labs", "Abnormal labs"),
        ("draft_clinician_note_outline", "Draft clinician note outline"),
    ],
    "trend_review": [
        ("patient_snapshot", "Patient snapshot"),
        ("lab_trends", "Lab trends"),
        ("abnormal_labs", "Abnormal labs"),
    ],
    "med_reconciliation": [
        ("patient_snapshot", "Patient snapshot"),
        ("medication_reconciliation", "Medication reconciliation"),
        ("record_search", "Record search"),
    ],
    "data_quality": [
        ("provider_sync_health", "Provider sync health"),
        ("recent_documents", "Recent documents"),
        ("record_search", "Record search"),
    ],
}


def _json_dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def _json_loads(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _preview(text: str | None, max_chars: int = 220) -> str | None:
    if not text:
        return None
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return f"{collapsed[: max_chars - 3].rstrip()}..."


def _extract_terms(prompt: str) -> list[str]:
    terms = []
    for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", prompt.lower()):
        if token not in STOPWORDS:
            terms.append(token)
    deduped: list[str] = []
    for term in terms:
        if term not in deduped:
            deduped.append(term)
    return deduped[:8]


class _CitationModel(BaseModel):
    source_type: str
    source_id: int | None = None
    label: str | None = None
    detail: str | None = None


class _PatientSnapshotOutput(BaseModel):
    patient_id: int
    patient_name: str
    age: int | None = None
    gender: str | None = None
    counts: dict[str, int]


class _DocumentItem(BaseModel):
    document_id: int
    title: str
    document_type: str
    received_at: datetime | None = None
    processing_status: str


class _RecentDocumentsOutput(BaseModel):
    total_documents: int = 0
    items: list[_DocumentItem] = Field(default_factory=list)


class _RecordMatchItem(BaseModel):
    source_type: str
    source_id: int
    title: str
    snippet: str
    created_at: datetime | None = None


class _RecordSearchOutput(BaseModel):
    query_terms: list[str] = Field(default_factory=list)
    total_matches: int = 0
    matches: list[_RecordMatchItem] = Field(default_factory=list)


class _AbnormalLabItem(BaseModel):
    lab_result_id: int
    test_name: str
    value_text: str | None = None
    status: str | None = None
    reference_range: str | None = None
    collected_at: datetime | None = None


class _AbnormalLabsOutput(BaseModel):
    total_abnormal: int = 0
    items: list[_AbnormalLabItem] = Field(default_factory=list)


class _LabTrendItem(BaseModel):
    metric_name: str
    latest_value: float
    previous_value: float
    unit: str | None = None
    latest_at: datetime | None = None
    previous_at: datetime | None = None
    delta: float
    direction: str
    latest_lab_result_id: int
    previous_lab_result_id: int


class _LabTrendsOutput(BaseModel):
    total_trends: int = 0
    items: list[_LabTrendItem] = Field(default_factory=list)


class _MedicationItem(BaseModel):
    medication_id: int
    name: str
    dosage: str | None = None
    frequency: str | None = None
    status: str | None = None
    prescribed_at: datetime | None = None


class _MedicationReconciliationOutput(BaseModel):
    active_medications: list[_MedicationItem] = Field(default_factory=list)
    recent_changes: list[_MedicationItem] = Field(default_factory=list)


class _ConnectionHealthItem(BaseModel):
    connection_id: int
    provider_name: str
    provider_slug: str
    status: str
    source_count: int
    last_error: str | None = None
    last_synced_at: datetime | None = None


class _ConnectionEventItem(BaseModel):
    event_id: int
    provider_slug: str
    event_type: str
    created_at: datetime
    details: str | None = None
    last_error: str | None = None


class _ProviderSyncHealthOutput(BaseModel):
    connections: list[_ConnectionHealthItem] = Field(default_factory=list)
    recent_failures: list[_ConnectionEventItem] = Field(default_factory=list)


class _DraftNoteSection(BaseModel):
    heading: str
    bullets: list[str] = Field(default_factory=list)


class _DraftClinicianNoteOutlineOutput(BaseModel):
    sections: list[_DraftNoteSection] = Field(default_factory=list)


@dataclass
class _ToolExecutionResult:
    tool_name: str
    title: str
    output_model: BaseModel
    citations: list[ClinicianAgentCitation]
    output_summary: str
    safety_flags: list[str]


class ClinicianCopilotService:
    """Persisted, deterministic clinician copilot runtime."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_run(
        self,
        *,
        patient_id: int,
        clinician_user_id: int,
        prompt: str,
        template: str,
        conversation_id: str | None = None,
    ) -> ClinicianAgentRunResponse:
        run = ClinicianAgentRun(
            patient_id=patient_id,
            clinician_user_id=clinician_user_id,
            conversation_id=conversation_id,
            template=template,
            prompt=prompt,
            status="running",
        )
        self.db.add(run)
        await self.db.flush()

        tool_outputs: dict[str, BaseModel] = {}
        step_rows: list[ClinicianAgentStep] = []

        try:
            for index, (tool_name, title) in enumerate(
                TEMPLATE_DEFINITIONS[template],
                start=1,
            ):
                result = await self._execute_tool(
                    tool_name=tool_name,
                    title=title,
                    patient_id=patient_id,
                    prompt=prompt,
                    prior_outputs=tool_outputs,
                )
                tool_outputs[tool_name] = result.output_model
                step_row = ClinicianAgentStep(
                    run_id=run.id,
                    step_order=index,
                    tool_name=tool_name,
                    title=title,
                    status="completed",
                    input_json=_json_dumps(
                        {
                            "patient_id": patient_id,
                            "prompt": prompt,
                            "prior_output_keys": sorted(tool_outputs.keys()),
                        }
                    ),
                    output_json=_json_dumps(result.output_model.model_dump(mode="json")),
                    output_summary=result.output_summary,
                    citations_json=_json_dumps(
                        [citation.model_dump(mode="json") for citation in result.citations]
                    ),
                    safety_flags_json=_json_dumps(result.safety_flags),
                )
                self.db.add(step_row)
                step_rows.append(step_row)
                await self.db.flush()

            final_answer = self._compose_final_answer(
                template=template,
                prompt=prompt,
                outputs=tool_outputs,
            )
            suggestions = self._build_suggestions(
                patient_id=patient_id,
                outputs=tool_outputs,
            )
            citations = self._collect_citations(step_rows)
            safety_flags = self._collect_safety_flags(step_rows, tool_outputs)

            for order, suggestion in enumerate(suggestions, start=1):
                self.db.add(
                    ClinicianAgentSuggestion(
                        run_id=run.id,
                        suggestion_order=order,
                        kind=suggestion.kind,
                        title=suggestion.title,
                        description=suggestion.description,
                        action_label=suggestion.action_label,
                        action_target=suggestion.action_target,
                        citations_json=_json_dumps(
                            [citation.model_dump(mode="json") for citation in suggestion.citations]
                        ),
                    )
                )

            run.status = "completed"
            run.final_answer = final_answer
            run.final_citations_json = _json_dumps(
                [citation.model_dump(mode="json") for citation in citations]
            )
            run.safety_flags_json = _json_dumps(safety_flags)
            run.completed_at = datetime.now(UTC)
            await self.db.commit()
            await self.db.refresh(run)
            return await self.get_run(run.id, clinician_user_id=clinician_user_id)
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)[:1000]
            run.completed_at = datetime.now(UTC)
            await self.db.commit()
            raise

    async def get_run(
        self,
        run_id: int,
        *,
        clinician_user_id: int,
    ) -> ClinicianAgentRunResponse:
        run = await self.db.scalar(
            select(ClinicianAgentRun).where(
                ClinicianAgentRun.id == run_id,
                ClinicianAgentRun.clinician_user_id == clinician_user_id,
            )
        )
        if run is None:
            raise ValueError("Clinician copilot run not found")

        step_rows = (
            await self.db.execute(
                select(ClinicianAgentStep)
                .where(ClinicianAgentStep.run_id == run.id)
                .order_by(ClinicianAgentStep.step_order.asc())
            )
        ).scalars().all()
        suggestion_rows = (
            await self.db.execute(
                select(ClinicianAgentSuggestion)
                .where(ClinicianAgentSuggestion.run_id == run.id)
                .order_by(ClinicianAgentSuggestion.suggestion_order.asc())
            )
        ).scalars().all()

        return ClinicianAgentRunResponse(
            id=run.id,
            patient_id=run.patient_id,
            clinician_user_id=run.clinician_user_id,
            template=run.template,
            prompt=run.prompt,
            status=run.status,
            final_answer=run.final_answer,
            citations=self._parse_citations(run.final_citations_json),
            safety_flags=_json_loads(run.safety_flags_json, []),
            steps=[
                ClinicianAgentStepResponse(
                    id=step.id,
                    step_order=step.step_order,
                    tool_name=step.tool_name,
                    title=step.title,
                    status=step.status,
                    output_summary=step.output_summary,
                    citations=self._parse_citations(step.citations_json),
                    safety_flags=_json_loads(step.safety_flags_json, []),
                    output_payload=_json_loads(step.output_json, None),
                    error_message=step.error_message,
                    created_at=step.created_at,
                )
                for step in step_rows
            ],
            suggestions=[
                ClinicianAgentSuggestionResponse(
                    id=suggestion.id,
                    suggestion_order=suggestion.suggestion_order,
                    kind=suggestion.kind,
                    title=suggestion.title,
                    description=suggestion.description,
                    action_label=suggestion.action_label,
                    action_target=suggestion.action_target,
                    citations=self._parse_citations(suggestion.citations_json),
                    created_at=suggestion.created_at,
                )
                for suggestion in suggestion_rows
            ],
            error_message=run.error_message,
            created_at=run.created_at,
            completed_at=run.completed_at,
        )

    async def get_run_patient_id(
        self,
        run_id: int,
        *,
        clinician_user_id: int,
    ) -> int:
        patient_id = await self.db.scalar(
            select(ClinicianAgentRun.patient_id).where(
                ClinicianAgentRun.id == run_id,
                ClinicianAgentRun.clinician_user_id == clinician_user_id,
            )
        )
        if patient_id is None:
            raise ValueError("Clinician copilot run not found")
        return int(patient_id)

    async def list_runs(
        self,
        *,
        clinician_user_id: int,
        patient_id: int,
        limit: int = 10,
    ) -> list[ClinicianAgentRunSummaryResponse]:
        rows = (
            await self.db.execute(
                select(ClinicianAgentRun)
                .where(
                    ClinicianAgentRun.clinician_user_id == clinician_user_id,
                    ClinicianAgentRun.patient_id == patient_id,
                )
                .order_by(ClinicianAgentRun.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()

        return [
            ClinicianAgentRunSummaryResponse(
                id=row.id,
                patient_id=row.patient_id,
                clinician_user_id=row.clinician_user_id,
                template=row.template,
                prompt=row.prompt,
                status=row.status,
                final_answer_preview=_preview(row.final_answer),
                safety_flags=_json_loads(row.safety_flags_json, []),
                created_at=row.created_at,
                completed_at=row.completed_at,
            )
            for row in rows
        ]

    async def _execute_tool(
        self,
        *,
        tool_name: str,
        title: str,
        patient_id: int,
        prompt: str,
        prior_outputs: dict[str, BaseModel],
    ) -> _ToolExecutionResult:
        handler = getattr(self, f"_tool_{tool_name}")
        return await handler(
            title=title,
            patient_id=patient_id,
            prompt=prompt,
            prior_outputs=prior_outputs,
        )

    async def _tool_patient_snapshot(
        self,
        *,
        title: str,
        patient_id: int,
        prompt: str,
        prior_outputs: dict[str, BaseModel],
    ) -> _ToolExecutionResult:
        del prompt, prior_outputs
        patient = await self.db.scalar(select(Patient).where(Patient.id == patient_id))
        if patient is None:
            raise ValueError(f"Patient {patient_id} not found")
        counts = {
            "documents": int(
                await self.db.scalar(
                    select(func.count()).select_from(Document).where(Document.patient_id == patient_id)
                )
                or 0
            ),
            "records": int(
                await self.db.scalar(
                    select(func.count()).select_from(Record).where(Record.patient_id == patient_id)
                )
                or 0
            ),
            "labs": int(
                await self.db.scalar(
                    select(func.count()).select_from(LabResult).where(LabResult.patient_id == patient_id)
                )
                or 0
            ),
            "medications": int(
                await self.db.scalar(
                    select(func.count()).select_from(Medication).where(Medication.patient_id == patient_id)
                )
                or 0
            ),
            "connections": int(
                await self.db.scalar(
                    select(func.count())
                    .select_from(PatientDataConnection)
                    .where(PatientDataConnection.patient_id == patient_id)
                )
                or 0
            ),
        }
        output = _PatientSnapshotOutput(
            patient_id=patient.id,
            patient_name=patient.full_name,
            age=patient.age,
            gender=patient.gender,
            counts=counts,
        )
        summary = (
            f"{patient.full_name}: {counts['documents']} documents, "
            f"{counts['records']} records, {counts['labs']} labs, "
            f"{counts['medications']} medications."
        )
        return _ToolExecutionResult(
            tool_name="patient_snapshot",
            title=title,
            output_model=output,
            citations=[],
            output_summary=summary,
            safety_flags=[],
        )

    async def _tool_recent_documents(
        self,
        *,
        title: str,
        patient_id: int,
        prompt: str,
        prior_outputs: dict[str, BaseModel],
    ) -> _ToolExecutionResult:
        del prompt, prior_outputs
        rows = (
            await self.db.execute(
                select(Document)
                .where(Document.patient_id == patient_id)
                .order_by(Document.received_date.desc(), Document.id.desc())
                .limit(5)
            )
        ).scalars().all()
        total = int(
            await self.db.scalar(
                select(func.count()).select_from(Document).where(Document.patient_id == patient_id)
            )
            or 0
        )
        items = [
            _DocumentItem(
                document_id=row.id,
                title=row.title or row.original_filename,
                document_type=row.document_type,
                received_at=row.received_date,
                processing_status=row.processing_status,
            )
            for row in rows
        ]
        output = _RecentDocumentsOutput(total_documents=total, items=items)
        citations = [
            ClinicianAgentCitation(
                source_type="document",
                source_id=item.document_id,
                label=item.title,
                detail=item.document_type,
            )
            for item in items
        ]
        summary = "No documents found." if not items else f"{len(items)} recent documents reviewed."
        safety_flags = ["missing_documents"] if total == 0 else []
        return _ToolExecutionResult("recent_documents", title, output, citations, summary, safety_flags)

    async def _tool_abnormal_labs(
        self,
        *,
        title: str,
        patient_id: int,
        prompt: str,
        prior_outputs: dict[str, BaseModel],
    ) -> _ToolExecutionResult:
        del prompt, prior_outputs
        rows = (
            await self.db.execute(
                select(LabResult)
                .where(
                    LabResult.patient_id == patient_id,
                    or_(
                        LabResult.is_abnormal.is_(True),
                        LabResult.status.in_(("abnormal", "critical")),
                    ),
                )
                .order_by(
                    LabResult.collected_at.desc().nullslast(),
                    LabResult.resulted_at.desc().nullslast(),
                    LabResult.id.desc(),
                )
                .limit(5)
            )
        ).scalars().all()
        items = [
            _AbnormalLabItem(
                lab_result_id=row.id,
                test_name=row.test_name,
                value_text=" ".join(part for part in [row.value, row.unit] if part).strip() or None,
                status=row.status,
                reference_range=row.reference_range,
                collected_at=row.collected_at,
            )
            for row in rows
        ]
        output = _AbnormalLabsOutput(total_abnormal=len(items), items=items)
        citations = [
            ClinicianAgentCitation(
                source_type="lab_result",
                source_id=item.lab_result_id,
                label=item.test_name,
                detail=item.value_text,
            )
            for item in items
        ]
        summary = "No abnormal labs identified." if not items else f"{len(items)} abnormal lab results identified."
        return _ToolExecutionResult("abnormal_labs", title, output, citations, summary, [])

    async def _tool_lab_trends(
        self,
        *,
        title: str,
        patient_id: int,
        prompt: str,
        prior_outputs: dict[str, BaseModel],
    ) -> _ToolExecutionResult:
        del prior_outputs
        rows = (
            await self.db.execute(
                select(LabResult)
                .where(
                    LabResult.patient_id == patient_id,
                    LabResult.numeric_value.is_not(None),
                )
                .order_by(
                    LabResult.collected_at.desc().nullslast(),
                    LabResult.id.desc(),
                )
                .limit(40)
            )
        ).scalars().all()
        grouped: dict[str, list[LabResult]] = defaultdict(list)
        for row in rows:
            grouped[row.test_name.lower()].append(row)

        prioritized_terms = _extract_terms(prompt)
        ranked_groups = sorted(
            grouped.items(),
            key=lambda item: (
                0 if any(term in item[0] for term in prioritized_terms) else 1,
                -len(item[1]),
            ),
        )
        items: list[_LabTrendItem] = []
        for _group_name, values in ranked_groups:
            ordered = sorted(
                values,
                key=lambda row: (
                    row.collected_at or row.resulted_at or row.created_at,
                    row.id,
                ),
                reverse=True,
            )
            if len(ordered) < 2:
                continue
            latest = ordered[0]
            previous = ordered[1]
            if latest.numeric_value is None or previous.numeric_value is None:
                continue
            delta = float(latest.numeric_value) - float(previous.numeric_value)
            direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
            items.append(
                _LabTrendItem(
                    metric_name=latest.test_name,
                    latest_value=float(latest.numeric_value),
                    previous_value=float(previous.numeric_value),
                    unit=latest.unit or previous.unit,
                    latest_at=latest.collected_at or latest.resulted_at,
                    previous_at=previous.collected_at or previous.resulted_at,
                    delta=delta,
                    direction=direction,
                    latest_lab_result_id=latest.id,
                    previous_lab_result_id=previous.id,
                )
            )
            if len(items) == 3:
                break
        output = _LabTrendsOutput(total_trends=len(items), items=items)
        citations: list[ClinicianAgentCitation] = []
        for item in items:
            citations.append(
                ClinicianAgentCitation(
                    source_type="lab_result",
                    source_id=item.latest_lab_result_id,
                    label=item.metric_name,
                    detail=f"latest {item.latest_value:g}",
                )
            )
            citations.append(
                ClinicianAgentCitation(
                    source_type="lab_result",
                    source_id=item.previous_lab_result_id,
                    label=item.metric_name,
                    detail=f"previous {item.previous_value:g}",
                )
            )
        summary = "No comparable lab trends found." if not items else f"{len(items)} lab trends summarized."
        return _ToolExecutionResult("lab_trends", title, output, citations, summary, [])

    async def _tool_medication_reconciliation(
        self,
        *,
        title: str,
        patient_id: int,
        prompt: str,
        prior_outputs: dict[str, BaseModel],
    ) -> _ToolExecutionResult:
        del prompt, prior_outputs
        rows = (
            await self.db.execute(
                select(Medication)
                .where(Medication.patient_id == patient_id)
                .order_by(
                    Medication.is_active.desc(),
                    Medication.prescribed_at.desc().nullslast(),
                    Medication.id.desc(),
                )
                .limit(20)
            )
        ).scalars().all()
        active = [
            _MedicationItem(
                medication_id=row.id,
                name=row.name,
                dosage=row.dosage,
                frequency=row.frequency,
                status=row.status,
                prescribed_at=row.prescribed_at,
            )
            for row in rows
            if row.is_current
        ][:6]
        recent_changes = [
            _MedicationItem(
                medication_id=row.id,
                name=row.name,
                dosage=row.dosage,
                frequency=row.frequency,
                status=row.status,
                prescribed_at=row.prescribed_at,
            )
            for row in rows
            if not row.is_current
        ][:4]
        output = _MedicationReconciliationOutput(
            active_medications=active,
            recent_changes=recent_changes,
        )
        citations = [
            ClinicianAgentCitation(
                source_type="medication",
                source_id=item.medication_id,
                label=item.name,
                detail=item.status,
            )
            for item in [*active, *recent_changes]
        ]
        summary = (
            f"{len(active)} active medications; {len(recent_changes)} recent inactive/completed entries."
        )
        return _ToolExecutionResult("medication_reconciliation", title, output, citations, summary, [])

    async def _tool_provider_sync_health(
        self,
        *,
        title: str,
        patient_id: int,
        prompt: str,
        prior_outputs: dict[str, BaseModel],
    ) -> _ToolExecutionResult:
        del prompt, prior_outputs
        connections = (
            await self.db.execute(
                select(PatientDataConnection)
                .where(PatientDataConnection.patient_id == patient_id)
                .order_by(PatientDataConnection.provider_name.asc())
            )
        ).scalars().all()
        events = (
            await self.db.execute(
                select(PatientConnectionSyncEvent)
                .where(PatientConnectionSyncEvent.patient_id == patient_id)
                .order_by(PatientConnectionSyncEvent.created_at.desc())
                .limit(8)
            )
        ).scalars().all()
        connection_items = [
            _ConnectionHealthItem(
                connection_id=row.id,
                provider_name=row.provider_name,
                provider_slug=row.provider_slug,
                status=row.status,
                source_count=row.source_count,
                last_error=row.last_error,
                last_synced_at=row.last_synced_at,
            )
            for row in connections
        ]
        failure_items = [
            _ConnectionEventItem(
                event_id=row.id,
                provider_slug=row.provider_slug,
                event_type=row.event_type,
                created_at=row.created_at,
                details=row.details,
                last_error=row.last_error,
            )
            for row in events
            if row.event_type == "sync_failed" or row.last_error
        ]
        output = _ProviderSyncHealthOutput(
            connections=connection_items,
            recent_failures=failure_items,
        )
        citations = [
            ClinicianAgentCitation(
                source_type="connection",
                source_id=item.connection_id,
                label=item.provider_name,
                detail=item.status,
            )
            for item in connection_items
        ]
        citations.extend(
            ClinicianAgentCitation(
                source_type="connection_event",
                source_id=item.event_id,
                label=item.provider_slug,
                detail=item.event_type,
            )
            for item in failure_items
        )
        safety_flags = ["provider_sync_attention"] if failure_items else []
        summary = (
            "No provider connections configured."
            if not connection_items
            else f"{len(connection_items)} connections checked; {len(failure_items)} recent failures."
        )
        return _ToolExecutionResult("provider_sync_health", title, output, citations, summary, safety_flags)

    async def _tool_record_search(
        self,
        *,
        title: str,
        patient_id: int,
        prompt: str,
        prior_outputs: dict[str, BaseModel],
    ) -> _ToolExecutionResult:
        del prior_outputs
        terms = _extract_terms(prompt)
        record_rows = (
            await self.db.execute(
                select(Record)
                .where(Record.patient_id == patient_id)
                .order_by(Record.created_at.desc())
                .limit(25)
            )
        ).scalars().all()
        document_rows = (
            await self.db.execute(
                select(Document)
                .where(Document.patient_id == patient_id)
                .order_by(Document.received_date.desc())
                .limit(25)
            )
        ).scalars().all()

        candidates: list[tuple[int, _RecordMatchItem]] = []
        for row in record_rows:
            haystack = f"{row.title} {row.content}".lower()
            score = sum(haystack.count(term) for term in terms) if terms else 1
            if score <= 0:
                continue
            candidates.append(
                (
                    score,
                    _RecordMatchItem(
                        source_type="record",
                        source_id=row.id,
                        title=row.title,
                        snippet=_preview(row.content, 180) or row.title,
                        created_at=row.created_at,
                    ),
                )
            )
        for row in document_rows:
            haystack = " ".join(
                part
                for part in [
                    row.title or "",
                    row.description or "",
                    row.extracted_text or "",
                    row.original_filename,
                ]
            ).lower()
            score = sum(haystack.count(term) for term in terms) if terms else 1
            if score <= 0:
                continue
            snippet_source = row.description or row.extracted_text or row.original_filename
            candidates.append(
                (
                    score,
                    _RecordMatchItem(
                        source_type="document",
                        source_id=row.id,
                        title=row.title or row.original_filename,
                        snippet=_preview(snippet_source, 180) or (row.title or row.original_filename),
                        created_at=row.received_date,
                    ),
                )
            )

        candidates.sort(key=lambda item: (-item[0], item[1].created_at or datetime.min.replace(tzinfo=UTC)))
        matches = [item for _, item in candidates[:5]]
        output = _RecordSearchOutput(
            query_terms=terms,
            total_matches=len(matches),
            matches=matches,
        )
        citations = [
            ClinicianAgentCitation(
                source_type=item.source_type,
                source_id=item.source_id,
                label=item.title,
                detail=item.snippet,
            )
            for item in matches
        ]
        summary = "No relevant records found." if not matches else f"{len(matches)} matching records/documents."
        safety_flags = ["insufficient_record_context"] if not matches else []
        return _ToolExecutionResult("record_search", title, output, citations, summary, safety_flags)

    async def _tool_draft_clinician_note_outline(
        self,
        *,
        title: str,
        patient_id: int,
        prompt: str,
        prior_outputs: dict[str, BaseModel],
    ) -> _ToolExecutionResult:
        del patient_id, prompt
        snapshot = prior_outputs.get("patient_snapshot")
        docs = prior_outputs.get("recent_documents")
        abnormal_labs = prior_outputs.get("abnormal_labs")
        meds = prior_outputs.get("medication_reconciliation")
        sync = prior_outputs.get("provider_sync_health")

        sections: list[_DraftNoteSection] = []
        if isinstance(snapshot, _PatientSnapshotOutput):
            sections.append(
                _DraftNoteSection(
                    heading="Overview",
                    bullets=[
                        f"Patient: {snapshot.patient_name}",
                        f"Chart includes {snapshot.counts.get('documents', 0)} documents and {snapshot.counts.get('records', 0)} records.",
                    ],
                )
            )
        if isinstance(docs, _RecentDocumentsOutput):
            sections.append(
                _DraftNoteSection(
                    heading="Recent documents",
                    bullets=[
                        f"{item.title} ({item.document_type})"
                        for item in docs.items[:3]
                    ]
                    or ["Not in documents."],
                )
            )
        if isinstance(abnormal_labs, _AbnormalLabsOutput):
            sections.append(
                _DraftNoteSection(
                    heading="Abnormal labs",
                    bullets=[
                        f"{item.test_name}: {item.value_text or 'value not recorded'}"
                        for item in abnormal_labs.items[:3]
                    ]
                    or ["No abnormal labs identified."],
                )
            )
        if isinstance(meds, _MedicationReconciliationOutput):
            sections.append(
                _DraftNoteSection(
                    heading="Medication check",
                    bullets=[
                        f"Active: {item.name}"
                        for item in meds.active_medications[:4]
                    ]
                    or ["No active medications listed."],
                )
            )
        if isinstance(sync, _ProviderSyncHealthOutput) and sync.recent_failures:
            sections.append(
                _DraftNoteSection(
                    heading="Data quality follow-up",
                    bullets=[
                        f"{item.provider_slug}: {item.last_error or item.event_type}"
                        for item in sync.recent_failures[:3]
                    ],
                )
            )

        output = _DraftClinicianNoteOutlineOutput(sections=sections)
        citations = self._collect_output_citations(prior_outputs)
        summary = "Draft note outline prepared."
        return _ToolExecutionResult("draft_clinician_note_outline", title, output, citations, summary, [])

    def _compose_final_answer(
        self,
        *,
        template: str,
        prompt: str,
        outputs: dict[str, BaseModel],
    ) -> str:
        del prompt
        snapshot = outputs.get("patient_snapshot")
        docs = outputs.get("recent_documents")
        abnormal = outputs.get("abnormal_labs")
        trends = outputs.get("lab_trends")
        meds = outputs.get("medication_reconciliation")
        sync = outputs.get("provider_sync_health")
        outline = outputs.get("draft_clinician_note_outline")

        lines: list[str] = []

        if template == "chart_review":
            if isinstance(snapshot, _PatientSnapshotOutput):
                lines.append(
                    f"{snapshot.patient_name} chart review: "
                    f"{snapshot.counts.get('documents', 0)} documents, "
                    f"{snapshot.counts.get('records', 0)} records, "
                    f"{snapshot.counts.get('labs', 0)} labs."
                )
            if isinstance(docs, _RecentDocumentsOutput):
                if docs.items:
                    lines.append(
                        "Recent documents: "
                        + "; ".join(item.title for item in docs.items[:3])
                        + "."
                    )
                else:
                    lines.append("Not in documents.")
            if isinstance(abnormal, _AbnormalLabsOutput):
                if abnormal.items:
                    lines.append(
                        "Abnormal labs: "
                        + "; ".join(
                            f"{item.test_name} ({item.value_text or 'value not recorded'})"
                            for item in abnormal.items[:3]
                        )
                        + "."
                    )
                else:
                    lines.append("No abnormal labs identified in current records.")
            if isinstance(outline, _DraftClinicianNoteOutlineOutput) and outline.sections:
                lines.append(
                    "Draft note outline prepared with sections for overview, recent evidence, and follow-up."
                )

        elif template == "trend_review":
            if isinstance(trends, _LabTrendsOutput) and trends.items:
                lines.append(
                    "Trend review: "
                    + "; ".join(
                        f"{item.metric_name} {item.direction} by {item.delta:g} {item.unit or ''}".strip()
                        for item in trends.items
                    )
                    + "."
                )
            else:
                lines.append("Not in records.")
            if isinstance(abnormal, _AbnormalLabsOutput) and abnormal.items:
                lines.append(
                    "Concurrent abnormal labs: "
                    + "; ".join(item.test_name for item in abnormal.items[:3])
                    + "."
                )

        elif template == "med_reconciliation":
            if isinstance(meds, _MedicationReconciliationOutput):
                if meds.active_medications:
                    lines.append(
                        "Active medications: "
                        + "; ".join(item.name for item in meds.active_medications[:5])
                        + "."
                    )
                else:
                    lines.append("No active medications listed in current records.")
                if meds.recent_changes:
                    lines.append(
                        "Recent medication changes: "
                        + "; ".join(
                            f"{item.name} ({item.status or 'status unknown'})"
                            for item in meds.recent_changes[:4]
                        )
                        + "."
                    )
            search = outputs.get("record_search")
            if isinstance(search, _RecordSearchOutput) and search.matches:
                lines.append(
                    "Supporting record evidence: "
                    + "; ".join(item.title for item in search.matches[:3])
                    + "."
                )

        elif template == "data_quality":
            if isinstance(sync, _ProviderSyncHealthOutput):
                if sync.connections:
                    lines.append(
                        f"Data quality review: {len(sync.connections)} provider connections checked."
                    )
                if sync.recent_failures:
                    lines.append(
                        "Recent sync issues: "
                        + "; ".join(
                            f"{item.provider_slug} ({item.last_error or item.event_type})"
                            for item in sync.recent_failures[:3]
                        )
                        + "."
                    )
                else:
                    lines.append("No recent provider sync failures recorded.")
            search = outputs.get("record_search")
            if isinstance(search, _RecordSearchOutput) and not search.matches:
                lines.append("Not in records.")

        return "\n".join(lines) if lines else "Not in records."

    def _build_suggestions(
        self,
        *,
        patient_id: int,
        outputs: dict[str, BaseModel],
    ) -> list[ClinicianAgentSuggestionResponse]:
        suggestions: list[ClinicianAgentSuggestionResponse] = []
        abnormal = outputs.get("abnormal_labs")
        if isinstance(abnormal, _AbnormalLabsOutput) and abnormal.items:
            suggestions.append(
                ClinicianAgentSuggestionResponse(
                    id=0,
                    suggestion_order=0,
                    kind="review_abnormal_labs",
                    title="Review abnormal lab evidence",
                    description="Open the patient panel and compare the flagged labs against recent documents.",
                    action_label="Open patient panel",
                    action_target=f"patient:{patient_id}:panel",
                    citations=[
                        ClinicianAgentCitation(
                            source_type="lab_result",
                            source_id=item.lab_result_id,
                            label=item.test_name,
                            detail=item.value_text,
                        )
                        for item in abnormal.items[:3]
                    ],
                )
            )
        meds = outputs.get("medication_reconciliation")
        if isinstance(meds, _MedicationReconciliationOutput) and meds.active_medications:
            suggestions.append(
                ClinicianAgentSuggestionResponse(
                    id=0,
                    suggestion_order=0,
                    kind="verify_medication_list",
                    title="Verify active medication list",
                    description="Use the chat and records context to confirm active versus stopped medications before documenting reconciliation.",
                    action_label="Review records",
                    action_target=f"patient:{patient_id}:records",
                    citations=[
                        ClinicianAgentCitation(
                            source_type="medication",
                            source_id=item.medication_id,
                            label=item.name,
                            detail=item.status,
                        )
                        for item in meds.active_medications[:3]
                    ],
                )
            )
        sync = outputs.get("provider_sync_health")
        if isinstance(sync, _ProviderSyncHealthOutput) and sync.recent_failures:
            suggestions.append(
                ClinicianAgentSuggestionResponse(
                    id=0,
                    suggestion_order=0,
                    kind="review_data_quality",
                    title="Review provider sync failures",
                    description="Inspect connection status before relying on missing data as clinically meaningful absence.",
                    action_label="Open sync panel",
                    action_target=f"patient:{patient_id}:connections",
                    citations=[
                        ClinicianAgentCitation(
                            source_type="connection_event",
                            source_id=item.event_id,
                            label=item.provider_slug,
                            detail=item.last_error or item.event_type,
                        )
                        for item in sync.recent_failures[:3]
                    ],
                )
            )
        docs = outputs.get("recent_documents")
        if isinstance(docs, _RecentDocumentsOutput) and docs.total_documents == 0:
            suggestions.append(
                ClinicianAgentSuggestionResponse(
                    id=0,
                    suggestion_order=0,
                    kind="request_more_documents",
                    title="Request additional source documents",
                    description="There are no uploaded documents for this patient. Use the clinician workflow to request supporting files before relying on chat-only context.",
                    action_label="Request uploads",
                    action_target=f"patient:{patient_id}:documents",
                    citations=[],
                )
            )
        if not suggestions:
            suggestions.append(
                ClinicianAgentSuggestionResponse(
                    id=0,
                    suggestion_order=0,
                    kind="continue_review",
                    title="Continue chart review in workspace",
                    description="Use the current patient chat and panel to validate details before documenting a decision.",
                    action_label="Open workspace",
                    action_target=f"patient:{patient_id}:workspace",
                    citations=[],
                )
            )
        return suggestions[:4]

    def _collect_output_citations(
        self,
        outputs: dict[str, BaseModel],
    ) -> list[ClinicianAgentCitation]:
        citations: list[ClinicianAgentCitation] = []
        docs = outputs.get("recent_documents")
        if isinstance(docs, _RecentDocumentsOutput):
            citations.extend(
                ClinicianAgentCitation(
                    source_type="document",
                    source_id=item.document_id,
                    label=item.title,
                    detail=item.document_type,
                )
                for item in docs.items[:3]
            )
        abnormal = outputs.get("abnormal_labs")
        if isinstance(abnormal, _AbnormalLabsOutput):
            citations.extend(
                ClinicianAgentCitation(
                    source_type="lab_result",
                    source_id=item.lab_result_id,
                    label=item.test_name,
                    detail=item.value_text,
                )
                for item in abnormal.items[:3]
            )
        return citations

    def _collect_citations(
        self,
        step_rows: list[ClinicianAgentStep],
    ) -> list[ClinicianAgentCitation]:
        deduped: dict[tuple[str, int | None, str | None], ClinicianAgentCitation] = {}
        for step in step_rows:
            for citation in self._parse_citations(step.citations_json):
                key = (citation.source_type, citation.source_id, citation.label)
                deduped[key] = citation
        return list(deduped.values())[:12]

    def _collect_safety_flags(
        self,
        step_rows: list[ClinicianAgentStep],
        outputs: dict[str, BaseModel],
    ) -> list[str]:
        flags: list[str] = []
        for step in step_rows:
            for flag in _json_loads(step.safety_flags_json, []):
                if flag not in flags:
                    flags.append(flag)
        docs = outputs.get("recent_documents")
        search = outputs.get("record_search")
        if isinstance(docs, _RecentDocumentsOutput) and docs.total_documents == 0:
            if "missing_documents" not in flags:
                flags.append("missing_documents")
        if isinstance(search, _RecordSearchOutput) and not search.matches:
            if "insufficient_record_context" not in flags:
                flags.append("insufficient_record_context")
        return flags

    def _parse_citations(self, value: str | None) -> list[ClinicianAgentCitation]:
        return [ClinicianAgentCitation(**item) for item in _json_loads(value, []) if isinstance(item, dict)]
