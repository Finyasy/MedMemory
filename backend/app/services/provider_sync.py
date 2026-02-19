"""Provider sync adapters for background connection maintenance.

Adapters support:
- deterministic local delta scans against already-ingested records
- live FHIR sync from configured provider APIs (DHA/KHIS/SHR and partners)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

import requests
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Document,
    Encounter,
    LabResult,
    Medication,
    Patient,
    PatientDataConnection,
)
from app.services.ingestion.encounters import EncounterIngestionService
from app.services.ingestion.labs import LabIngestionService
from app.services.ingestion.medications import MedicationIngestionService

logger = logging.getLogger(__name__)


@dataclass
class ProviderSyncResult:
    """Result returned by a provider sync adapter."""

    source_count_total: int
    source_count_delta: int
    details: str


@dataclass
class ProviderSyncValidationResult:
    """Dry-run validation result for live provider connectivity."""

    ok: bool
    mode: str
    provider_key: str | None
    base_url: str | None
    patient_ref: str | None
    counts: dict[str, int]
    details: str


@dataclass(frozen=True)
class LiveProviderConfig:
    """Resolved runtime configuration for one live provider endpoint."""

    provider_key: str
    base_url: str
    bearer_token: str | None
    api_key: str | None
    timeout_seconds: int
    verify_ssl: bool


class ProviderSyncAdapter(Protocol):
    """Contract for provider-specific incremental sync adapters."""

    async def sync(
        self,
        *,
        db: AsyncSession,
        connection: PatientDataConnection,
        now: datetime,
    ) -> ProviderSyncResult:
        """Run one incremental sync for the given connection."""


def _provider_tokens(provider_slug: str, provider_name: str) -> list[str]:
    tokens: set[str] = set()
    for raw in (provider_slug, provider_name):
        value = (raw or "").strip().lower()
        if not value:
            continue
        tokens.add(value)
        for token in re.split(r"[^a-z0-9]+", value):
            if len(token) >= 3:
                tokens.add(token)
    return sorted(tokens, key=len, reverse=True)[:12]


def _normalize_mapping(values: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in (values or {}).items():
        norm_key = str(key or "").strip().lower()
        norm_value = str(value or "").strip()
        if norm_key and norm_value:
            normalized[norm_key] = norm_value
    return normalized


def _lookup_provider_value(
    values: dict[str, str],
    *,
    provider_slug: str,
    provider_name: str,
) -> tuple[str | None, str | None]:
    normalized = _normalize_mapping(values)
    if not normalized:
        return None, None

    slug = (provider_slug or "").strip().lower()
    if slug and slug in normalized:
        return slug, normalized[slug]

    tokens = _provider_tokens(provider_slug, provider_name)
    for token in tokens:
        if token in normalized:
            return token, normalized[token]

    for key, value in normalized.items():
        if slug and (key in slug or slug in key):
            return key, value

    for key, value in normalized.items():
        if any(token in key for token in tokens):
            return key, value

    return None, None


def _match_any_token(columns, tokens: list[str]):
    if not tokens:
        return None
    expressions = []
    for column in columns:
        for token in tokens:
            expressions.append(func.lower(func.coalesce(column, "")).like(f"%{token}%"))
    if not expressions:
        return None
    return or_(*expressions)


def _created_after_fallback(
    primary_ts_col,
    created_ts_col,
    since: datetime | None,
):
    if since is None:
        return None
    return or_(
        primary_ts_col > since,
        and_(primary_ts_col.is_(None), created_ts_col > since),
    )


async def _count_records(
    *,
    db: AsyncSession,
    model,
    patient_id: int,
    provider_match_clause,
    since_clause=None,
) -> int:
    filters = [model.patient_id == patient_id]
    if provider_match_clause is not None:
        filters.append(provider_match_clause)
    if since_clause is not None:
        filters.append(since_clause)
    count = await db.scalar(select(func.count()).select_from(model).where(*filters))
    return int(count or 0)


async def _count_records_for_source_system(
    *,
    db: AsyncSession,
    patient_id: int,
    source_system: str,
) -> int:
    if not source_system:
        return 0
    total = 0
    for model in (LabResult, Medication, Encounter, Document):
        count = await db.scalar(
            select(func.count())
            .select_from(model)
            .where(
                and_(
                    model.patient_id == patient_id,
                    func.lower(func.coalesce(model.source_system, ""))
                    == source_system.lower(),
                )
            )
        )
        total += int(count or 0)
    return total


class LocalDeltaScanAdapter:
    """Local adapter: infer provider sync delta from already ingested records."""

    async def sync(
        self,
        *,
        db: AsyncSession,
        connection: PatientDataConnection,
        now: datetime,
    ) -> ProviderSyncResult:
        tokens = _provider_tokens(connection.provider_slug, connection.provider_name)
        since = connection.last_synced_at

        lab_match = _match_any_token(
            [LabResult.source_system, LabResult.performing_lab, LabResult.ordering_provider],
            tokens,
        )
        med_match = _match_any_token(
            [Medication.source_system, Medication.prescriber, Medication.pharmacy],
            tokens,
        )
        encounter_match = _match_any_token(
            [Encounter.source_system, Encounter.provider_name, Encounter.facility],
            tokens,
        )
        doc_match = _match_any_token(
            [Document.source_system, Document.author, Document.facility, Document.title],
            tokens,
        )

        labs_total = await _count_records(
            db=db,
            model=LabResult,
            patient_id=connection.patient_id,
            provider_match_clause=lab_match,
        )
        labs_delta = await _count_records(
            db=db,
            model=LabResult,
            patient_id=connection.patient_id,
            provider_match_clause=lab_match,
            since_clause=_created_after_fallback(
                LabResult.collected_at,
                LabResult.created_at,
                since,
            ),
        )

        meds_total = await _count_records(
            db=db,
            model=Medication,
            patient_id=connection.patient_id,
            provider_match_clause=med_match,
        )
        meds_delta = await _count_records(
            db=db,
            model=Medication,
            patient_id=connection.patient_id,
            provider_match_clause=med_match,
            since_clause=_created_after_fallback(
                Medication.prescribed_at,
                Medication.created_at,
                since,
            ),
        )

        encounters_total = await _count_records(
            db=db,
            model=Encounter,
            patient_id=connection.patient_id,
            provider_match_clause=encounter_match,
        )
        encounters_delta = await _count_records(
            db=db,
            model=Encounter,
            patient_id=connection.patient_id,
            provider_match_clause=encounter_match,
            since_clause=_created_after_fallback(
                Encounter.encounter_date,
                Encounter.created_at,
                since,
            ),
        )

        docs_total = await _count_records(
            db=db,
            model=Document,
            patient_id=connection.patient_id,
            provider_match_clause=doc_match,
        )
        docs_delta = await _count_records(
            db=db,
            model=Document,
            patient_id=connection.patient_id,
            provider_match_clause=doc_match,
            since_clause=or_(
                _created_after_fallback(Document.document_date, Document.created_at, since),
                _created_after_fallback(Document.received_date, Document.created_at, since),
            )
            if since is not None
            else None,
        )

        total = labs_total + meds_total + encounters_total + docs_total
        delta = labs_delta + meds_delta + encounters_delta + docs_delta
        details = (
            f"delta={delta} total={total} "
            f"(labs +{labs_delta}/{labs_total}, meds +{meds_delta}/{meds_total}, "
            f"encounters +{encounters_delta}/{encounters_total}, docs +{docs_delta}/{docs_total})"
        )
        return ProviderSyncResult(
            source_count_total=total,
            source_count_delta=delta,
            details=details,
        )


def _resolve_live_provider_config(
    connection: PatientDataConnection,
) -> LiveProviderConfig | None:
    if not settings.provider_sync_live_enabled:
        return None

    lookup_key, base_url = _lookup_provider_value(
        settings.provider_sync_live_base_urls,
        provider_slug=connection.provider_slug,
        provider_name=connection.provider_name,
    )
    if not base_url:
        return None

    _, bearer_token = _lookup_provider_value(
        settings.provider_sync_live_bearer_tokens,
        provider_slug=connection.provider_slug,
        provider_name=connection.provider_name,
    )
    _, api_key = _lookup_provider_value(
        settings.provider_sync_live_api_keys,
        provider_slug=connection.provider_slug,
        provider_name=connection.provider_name,
    )

    resolved_key = lookup_key or connection.provider_slug
    return LiveProviderConfig(
        provider_key=resolved_key,
        base_url=base_url.rstrip("/"),
        bearer_token=bearer_token,
        api_key=api_key,
        timeout_seconds=settings.provider_sync_live_timeout_seconds,
        verify_ssl=settings.provider_sync_live_verify_ssl,
    )


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    dt = _coerce_datetime(value)
    if dt is not None:
        return dt.date()
    if isinstance(value, str):
        text = value.strip()
        if len(text) >= 10:
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                return None
    return None


def _fhir_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    as_utc = value.astimezone(UTC)
    return as_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _value_from_reference(ref: dict[str, Any] | None) -> str | None:
    if not isinstance(ref, dict):
        return None
    display = ref.get("display")
    if isinstance(display, str) and display.strip():
        return display.strip()
    reference = ref.get("reference")
    if isinstance(reference, str) and reference.strip():
        return reference.strip()
    return None


def _first_non_empty(values: list[str | None]) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_coding(concept: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not isinstance(concept, dict):
        return None, None
    text = concept.get("text")
    if isinstance(text, str) and text.strip():
        text = text.strip()
    else:
        text = None

    coding = concept.get("coding")
    if not isinstance(coding, list):
        return text, None

    for item in coding:
        if not isinstance(item, dict):
            continue
        display = item.get("display")
        code = item.get("code")
        resolved_display = display.strip() if isinstance(display, str) and display.strip() else None
        resolved_code = code.strip() if isinstance(code, str) and code.strip() else None
        if resolved_display or resolved_code:
            return resolved_display or text, resolved_code
    return text, None


def _extract_note_text(resource: dict[str, Any]) -> str | None:
    notes = resource.get("note")
    if not isinstance(notes, list):
        return None
    parts: list[str] = []
    for note in notes:
        if not isinstance(note, dict):
            continue
        text = note.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    if not parts:
        return None
    return "\n".join(parts)


def _extract_reference_range(resource: dict[str, Any]) -> str | None:
    ranges = resource.get("referenceRange")
    if not isinstance(ranges, list) or not ranges:
        return None
    first_range = ranges[0]
    if not isinstance(first_range, dict):
        return None

    low = first_range.get("low") if isinstance(first_range.get("low"), dict) else {}
    high = first_range.get("high") if isinstance(first_range.get("high"), dict) else {}

    low_value = low.get("value")
    high_value = high.get("value")
    unit = (
        high.get("unit")
        if isinstance(high.get("unit"), str)
        else low.get("unit")
        if isinstance(low.get("unit"), str)
        else None
    )

    if low_value is None and high_value is None:
        text = first_range.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        return None

    low_text = str(low_value) if low_value is not None else ""
    high_text = str(high_value) if high_value is not None else ""
    if low_text and high_text:
        base = f"{low_text}-{high_text}"
    elif low_text:
        base = f">= {low_text}"
    else:
        base = f"<= {high_text}"

    if isinstance(unit, str) and unit.strip():
        return f"{base} {unit.strip()}"
    return base


def _extract_interpretation_flags(resource: dict[str, Any]) -> tuple[bool, bool]:
    interpretation = resource.get("interpretation")
    if not isinstance(interpretation, list):
        return False, False

    abnormal_codes = {"H", "HH", "L", "LL", "A", "AA", "POS", "DET", "ABN"}
    critical_codes = {"HH", "LL", "AA", "CRIT", "CRITICAL"}
    seen_codes: set[str] = set()

    for item in interpretation:
        if not isinstance(item, dict):
            continue
        coding = item.get("coding")
        if not isinstance(coding, list):
            continue
        for code_item in coding:
            if not isinstance(code_item, dict):
                continue
            raw = code_item.get("code")
            if isinstance(raw, str) and raw.strip():
                seen_codes.add(raw.strip().upper())

    is_critical = any(code in critical_codes for code in seen_codes)
    is_abnormal = is_critical or any(code in abnormal_codes for code in seen_codes)
    return is_abnormal, is_critical


def _map_observation_status(
    fhir_status: str | None,
    *,
    is_abnormal: bool,
    is_critical: bool,
) -> str:
    if is_critical:
        return "critical"
    if is_abnormal:
        return "abnormal"

    normalized = (fhir_status or "").strip().lower()
    if normalized in {"registered", "preliminary"}:
        return "pending"
    if normalized in {"entered-in-error", "cancelled"}:
        return "pending"
    return "normal"


def _map_medication_status(fhir_status: str | None) -> tuple[str, bool]:
    normalized = (fhir_status or "").strip().lower()
    if normalized in {"active", "draft", "unknown"}:
        return "active", True
    if normalized in {"on-hold", "on_hold"}:
        return "on-hold", True
    if normalized in {"completed"}:
        return "completed", False
    if normalized in {"cancelled", "entered-in-error", "entered_in_error"}:
        return "cancelled", False
    if normalized in {"stopped"}:
        return "discontinued", False
    return "active", True


def _map_encounter_status(fhir_status: str | None) -> str:
    normalized = (fhir_status or "").strip().lower()
    mapping = {
        "planned": "scheduled",
        "arrived": "in-progress",
        "triaged": "in-progress",
        "in-progress": "in-progress",
        "onleave": "in-progress",
        "finished": "completed",
        "cancelled": "cancelled",
        "entered-in-error": "cancelled",
    }
    return mapping.get(normalized, "completed")


def _map_encounter_type(resource: dict[str, Any]) -> str:
    class_obj = resource.get("class")
    if isinstance(class_obj, dict):
        code = class_obj.get("code")
        if isinstance(code, str):
            normalized = code.strip().upper()
            if normalized == "IMP":
                return "inpatient"
            if normalized == "AMB":
                return "outpatient"
            if normalized == "EMER":
                return "emergency"
            if normalized == "VR":
                return "telehealth"
            if normalized == "HH":
                return "home_visit"

    encounter_type = resource.get("type")
    if isinstance(encounter_type, list) and encounter_type:
        first = encounter_type[0]
        if isinstance(first, dict):
            text, _ = _extract_coding(first)
            if text:
                lowered = text.lower()
                if "urgent" in lowered:
                    return "urgent_care"
                if "tele" in lowered or "virtual" in lowered:
                    return "telehealth"
                if "follow" in lowered:
                    return "follow_up"
                if "lab" in lowered:
                    return "lab_visit"
                if "consult" in lowered:
                    return "consultation"

    return "office_visit"


def _extract_fhir_bundle_resources(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    entries = bundle.get("entry")
    if not isinstance(entries, list):
        return []
    resources: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if isinstance(resource, dict):
            resources.append(resource)
    return resources


def _extract_bundle_next_url(bundle: dict[str, Any]) -> str | None:
    links = bundle.get("link")
    if not isinstance(links, list):
        return None
    for link in links:
        if not isinstance(link, dict):
            continue
        relation = link.get("relation")
        url = link.get("url")
        if relation == "next" and isinstance(url, str) and url.strip():
            return url.strip()
    return None


def _build_request_headers(config: LiveProviderConfig) -> dict[str, str]:
    headers = {
        "Accept": "application/fhir+json, application/json",
        "Content-Type": "application/fhir+json",
    }
    if config.bearer_token:
        headers["Authorization"] = f"Bearer {config.bearer_token}"
    if config.api_key:
        headers["X-API-Key"] = config.api_key
    return headers


async def _http_get_json(
    *,
    config: LiveProviderConfig,
    url: str,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    headers = _build_request_headers(config)

    def _request() -> dict[str, Any]:
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=config.timeout_seconds,
                verify=config.verify_ssl,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Provider request failed for {url}: {exc}") from exc

        if response.status_code >= 400:
            snippet = response.text.strip().replace("\n", " ")[:240]
            raise RuntimeError(
                f"Provider request returned HTTP {response.status_code} for {url}: {snippet}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Provider response for {url} is not valid JSON") from exc

        if not isinstance(payload, dict):
            raise RuntimeError(f"Provider response for {url} is not a JSON object")
        return payload

    return await asyncio.to_thread(_request)


async def _fetch_fhir_resources(
    *,
    config: LiveProviderConfig,
    resource_type: str,
    patient_ref: str,
    since: datetime | None,
) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    params: dict[str, str] = {
        "_count": str(settings.provider_sync_live_page_size),
        "_sort": "-_lastUpdated",
    }
    if since is not None:
        since_token = _fhir_timestamp(since)
        if since_token:
            params["_lastUpdated"] = f"ge{since_token}"

    primary_param = "subject"
    fallback_param = "patient"
    next_url = f"{config.base_url}/{resource_type.lstrip('/')}"
    page_count = 0

    for param_name in (primary_param, fallback_param):
        current_resources: list[dict[str, Any]] = []
        current_next_url = next_url
        request_params = dict(params)
        request_params[param_name] = patient_ref
        page_count = 0
        try:
            while current_next_url and page_count < settings.provider_sync_live_max_pages_per_resource:
                bundle = await _http_get_json(
                    config=config,
                    url=current_next_url,
                    params=request_params,
                )
                current_resources.extend(_extract_fhir_bundle_resources(bundle))
                current_next_url = _extract_bundle_next_url(bundle)
                request_params = None
                page_count += 1
            resources = current_resources
            break
        except RuntimeError as exc:
            if param_name == fallback_param:
                raise
            logger.warning(
                "FHIR %s fetch with '%s' parameter failed for %s: %s",
                resource_type,
                param_name,
                config.provider_key,
                exc,
            )
            continue

    return resources


async def _fetch_fhir_resource_count(
    *,
    config: LiveProviderConfig,
    resource_type: str,
    patient_ref: str,
) -> int:
    base_url = f"{config.base_url}/{resource_type.lstrip('/')}"
    base_params = {"_summary": "count"}

    for param_name in ("subject", "patient"):
        params = dict(base_params)
        params[param_name] = patient_ref
        try:
            bundle = await _http_get_json(
                config=config,
                url=base_url,
                params=params,
            )
        except RuntimeError:
            if param_name == "patient":
                raise
            continue

        total = bundle.get("total")
        if isinstance(total, int):
            return total
        return len(_extract_fhir_bundle_resources(bundle))

    return 0


async def _search_fhir_patient_id(
    *,
    config: LiveProviderConfig,
    identifier: str,
) -> str | None:
    if not identifier:
        return None

    search_value = identifier.strip()
    if settings.provider_sync_live_patient_identifier_system:
        search_value = (
            f"{settings.provider_sync_live_patient_identifier_system.strip()}|{search_value}"
        )

    url = f"{config.base_url}/Patient"
    bundle = await _http_get_json(
        config=config,
        url=url,
        params={
            "identifier": search_value,
            "_count": "1",
        },
    )

    resources = _extract_fhir_bundle_resources(bundle)
    if not resources:
        return None

    patient_resource = resources[0]
    patient_id = patient_resource.get("id")
    if isinstance(patient_id, str) and patient_id.strip():
        return patient_id.strip()
    return None


async def _resolve_patient_reference(
    *,
    db: AsyncSession,
    connection: PatientDataConnection,
    config: LiveProviderConfig,
) -> str:
    patient = await db.scalar(select(Patient).where(Patient.id == connection.patient_id))
    if patient is None:
        raise ValueError(f"Patient {connection.patient_id} does not exist")

    candidate_identifiers: list[str] = []
    if patient.external_id:
        candidate_identifiers.append(patient.external_id)
    candidate_identifiers.append(str(patient.id))

    for identifier in candidate_identifiers:
        try:
            fhir_patient_id = await _search_fhir_patient_id(
                config=config,
                identifier=identifier,
            )
        except RuntimeError as exc:
            logger.warning(
                "Patient search failed for provider=%s identifier=%s: %s",
                config.provider_key,
                identifier,
                exc,
            )
            break
        if fhir_patient_id:
            return f"Patient/{fhir_patient_id}"

    # Fall back to using external_id as FHIR id when search is unavailable.
    if patient.external_id:
        return f"Patient/{patient.external_id}"

    return f"Patient/{patient.id}"


async def _record_exists_by_source(
    *,
    db: AsyncSession,
    model,
    patient_id: int,
    source_system: str,
    source_id: str | None,
) -> bool:
    if not source_id:
        return False
    exists_stmt = select(model.id).where(
        and_(
            model.patient_id == patient_id,
            func.lower(func.coalesce(model.source_system, "")) == source_system.lower(),
            model.source_id == source_id,
        )
    )
    return (await db.scalar(exists_stmt)) is not None


def _map_observation_to_lab_payload(
    *,
    connection: PatientDataConnection,
    resource: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(resource, dict):
        return None

    source_id = resource.get("id")
    if not isinstance(source_id, str) or not source_id.strip():
        return None

    code_obj = resource.get("code") if isinstance(resource.get("code"), dict) else {}
    test_name, test_code = _extract_coding(code_obj)
    if not test_name:
        test_name = "FHIR Observation"

    value_quantity = (
        resource.get("valueQuantity")
        if isinstance(resource.get("valueQuantity"), dict)
        else {}
    )
    numeric_value = value_quantity.get("value")
    numeric_value = (
        float(numeric_value)
        if isinstance(numeric_value, (int, float))
        else None
    )
    unit = (
        value_quantity.get("unit")
        if isinstance(value_quantity.get("unit"), str)
        else None
    )

    value: str | None = None
    if numeric_value is not None:
        value = str(numeric_value)
    elif isinstance(resource.get("valueString"), str) and resource.get("valueString").strip():
        value = resource.get("valueString").strip()
    elif isinstance(resource.get("valueCodeableConcept"), dict):
        coded_text, _ = _extract_coding(resource.get("valueCodeableConcept"))
        value = coded_text

    effective_at = _coerce_datetime(resource.get("effectiveDateTime"))
    if effective_at is None:
        effective_period = (
            resource.get("effectivePeriod")
            if isinstance(resource.get("effectivePeriod"), dict)
            else {}
        )
        effective_at = _coerce_datetime(effective_period.get("start"))

    resulted_at = _coerce_datetime(resource.get("issued"))

    performer_names: list[str | None] = []
    performer = resource.get("performer")
    if isinstance(performer, list):
        for item in performer:
            performer_names.append(_value_from_reference(item if isinstance(item, dict) else None))

    is_abnormal, is_critical = _extract_interpretation_flags(resource)
    status = _map_observation_status(
        resource.get("status") if isinstance(resource.get("status"), str) else None,
        is_abnormal=is_abnormal,
        is_critical=is_critical,
    )

    category: str | None = None
    categories = resource.get("category")
    if isinstance(categories, list) and categories:
        first_category = categories[0]
        if isinstance(first_category, dict):
            category, _ = _extract_coding(first_category)

    return {
        "patient_id": connection.patient_id,
        "test_name": test_name,
        "test_code": test_code,
        "category": category,
        "value": value,
        "numeric_value": numeric_value,
        "unit": unit,
        "reference_range": _extract_reference_range(resource),
        "status": status,
        "collected_at": effective_at,
        "resulted_at": resulted_at,
        "notes": _extract_note_text(resource),
        "ordering_provider": _first_non_empty(
            [
                _value_from_reference(
                    resource.get("performer")[0]
                    if isinstance(resource.get("performer"), list)
                    and resource.get("performer")
                    and isinstance(resource.get("performer")[0], dict)
                    else None
                )
            ]
        ),
        "performing_lab": _first_non_empty(performer_names),
        "source_system": connection.provider_slug,
        "source_id": source_id.strip(),
    }


def _extract_dosage_quantity(
    dosage_instruction: dict[str, Any],
) -> tuple[float | None, str | None, str | None]:
    dose_and_rate = dosage_instruction.get("doseAndRate")
    if not isinstance(dose_and_rate, list) or not dose_and_rate:
        return None, None, None
    first = dose_and_rate[0]
    if not isinstance(first, dict):
        return None, None, None
    dose_quantity = first.get("doseQuantity")
    if not isinstance(dose_quantity, dict):
        return None, None, None
    value = dose_quantity.get("value")
    numeric = float(value) if isinstance(value, (int, float)) else None
    unit = dose_quantity.get("unit") if isinstance(dose_quantity.get("unit"), str) else None
    text = f"{numeric:g} {unit}".strip() if numeric is not None and unit else None
    return numeric, unit, text


def _extract_timing_frequency(dosage_instruction: dict[str, Any]) -> str | None:
    timing = dosage_instruction.get("timing")
    if not isinstance(timing, dict):
        return None
    repeat = timing.get("repeat")
    if not isinstance(repeat, dict):
        return None

    frequency = repeat.get("frequency")
    period = repeat.get("period")
    period_unit = repeat.get("periodUnit")
    bounds_period = repeat.get("boundsPeriod")

    parts: list[str] = []
    if isinstance(frequency, (int, float)):
        parts.append(f"{int(frequency)}x")
    if isinstance(period, (int, float)) and isinstance(period_unit, str) and period_unit.strip():
        parts.append(f"every {period:g} {period_unit.strip()}")
    elif isinstance(period_unit, str) and period_unit.strip():
        parts.append(f"per {period_unit.strip()}")

    if isinstance(bounds_period, dict):
        start = _coerce_datetime(bounds_period.get("start"))
        end = _coerce_datetime(bounds_period.get("end"))
        if start and end:
            parts.append(f"from {start.date().isoformat()} to {end.date().isoformat()}")

    if parts:
        return " ".join(parts)
    return None


def _extract_reason_codes(resource: dict[str, Any]) -> str | None:
    reason_codes = resource.get("reasonCode")
    if not isinstance(reason_codes, list):
        return None

    parts: list[str] = []
    for reason in reason_codes:
        if not isinstance(reason, dict):
            continue
        text, _ = _extract_coding(reason)
        if text:
            parts.append(text)
    if not parts:
        return None
    return "; ".join(parts)


def _map_medication_request_to_payload(
    *,
    connection: PatientDataConnection,
    resource: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(resource, dict):
        return None

    source_id = resource.get("id")
    if not isinstance(source_id, str) or not source_id.strip():
        return None

    medication_obj = (
        resource.get("medicationCodeableConcept")
        if isinstance(resource.get("medicationCodeableConcept"), dict)
        else {}
    )
    med_name, med_code = _extract_coding(medication_obj)
    if not med_name:
        med_name = "FHIR Medication"

    dosage_text: str | None = None
    dosage_value: float | None = None
    dosage_unit: str | None = None
    frequency: str | None = None
    route: str | None = None
    instructions: str | None = None

    dosage_instructions = resource.get("dosageInstruction")
    if isinstance(dosage_instructions, list) and dosage_instructions:
        first = dosage_instructions[0]
        if isinstance(first, dict):
            text = first.get("text")
            if isinstance(text, str) and text.strip():
                dosage_text = text.strip()
                instructions = dosage_text
            dosage_value, dosage_unit, fallback_text = _extract_dosage_quantity(first)
            if dosage_text is None:
                dosage_text = fallback_text
            frequency = _extract_timing_frequency(first)
            route_obj = first.get("route") if isinstance(first.get("route"), dict) else {}
            route_text, _ = _extract_coding(route_obj)
            route = route_text

    authored_on = _coerce_datetime(resource.get("authoredOn"))
    dispense_request = (
        resource.get("dispenseRequest")
        if isinstance(resource.get("dispenseRequest"), dict)
        else {}
    )
    validity_period = (
        dispense_request.get("validityPeriod")
        if isinstance(dispense_request.get("validityPeriod"), dict)
        else {}
    )

    start_date = _coerce_date(validity_period.get("start"))
    end_date = _coerce_date(validity_period.get("end"))
    if start_date is None and authored_on is not None:
        start_date = authored_on.date()

    requester = (
        resource.get("requester")
        if isinstance(resource.get("requester"), dict)
        else None
    )
    dispenser = (
        resource.get("dispenseRequest")
        if isinstance(resource.get("dispenseRequest"), dict)
        else None
    )

    status, is_active = _map_medication_status(
        resource.get("status") if isinstance(resource.get("status"), str) else None
    )

    return {
        "patient_id": connection.patient_id,
        "name": med_name,
        "drug_code": med_code,
        "dosage": dosage_text,
        "dosage_value": dosage_value,
        "dosage_unit": dosage_unit,
        "frequency": frequency,
        "route": route,
        "start_date": start_date,
        "end_date": end_date,
        "prescribed_at": authored_on,
        "is_active": is_active,
        "status": status,
        "prescriber": _value_from_reference(requester),
        "pharmacy": _value_from_reference(dispenser),
        "indication": _extract_reason_codes(resource),
        "instructions": instructions,
        "notes": _extract_note_text(resource),
        "source_system": connection.provider_slug,
        "source_id": source_id.strip(),
    }


def _extract_encounter_diagnoses(resource: dict[str, Any]) -> list[str] | None:
    diagnosis = resource.get("diagnosis")
    if not isinstance(diagnosis, list):
        return None

    rows: list[str] = []
    for item in diagnosis:
        if not isinstance(item, dict):
            continue
        condition = item.get("condition")
        value = _value_from_reference(condition if isinstance(condition, dict) else None)
        if value:
            rows.append(value)
    return rows or None


def _extract_encounter_provider(resource: dict[str, Any]) -> str | None:
    participants = resource.get("participant")
    if not isinstance(participants, list):
        return None
    for participant in participants:
        if not isinstance(participant, dict):
            continue
        individual = participant.get("individual")
        value = _value_from_reference(individual if isinstance(individual, dict) else None)
        if value:
            return value
    return None


def _map_encounter_to_payload(
    *,
    connection: PatientDataConnection,
    resource: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(resource, dict):
        return None

    source_id = resource.get("id")
    if not isinstance(source_id, str) or not source_id.strip():
        return None

    period = resource.get("period") if isinstance(resource.get("period"), dict) else {}
    encounter_date = _coerce_datetime(period.get("start"))
    if encounter_date is None:
        encounter_date = _coerce_datetime(resource.get("actualPeriod"))
    if encounter_date is None:
        encounter_date = datetime.now(UTC)

    service_provider = (
        resource.get("serviceProvider")
        if isinstance(resource.get("serviceProvider"), dict)
        else None
    )

    reason_for_visit = _extract_reason_codes(resource)
    diagnoses = _extract_encounter_diagnoses(resource)

    payload: dict[str, Any] = {
        "patient_id": connection.patient_id,
        "encounter_type": _map_encounter_type(resource),
        "encounter_date": encounter_date,
        "start_time": _coerce_datetime(period.get("start")),
        "end_time": _coerce_datetime(period.get("end")),
        "facility": _value_from_reference(service_provider),
        "location": None,
        "provider_name": _extract_encounter_provider(resource),
        "reason_for_visit": reason_for_visit,
        "diagnoses": diagnoses,
        "status": _map_encounter_status(
            resource.get("status") if isinstance(resource.get("status"), str) else None
        ),
        "source_system": connection.provider_slug,
        "source_id": source_id.strip(),
    }

    locations = resource.get("location")
    if isinstance(locations, list) and locations:
        first_location = locations[0]
        if isinstance(first_location, dict):
            loc_ref = first_location.get("location")
            payload["location"] = _value_from_reference(
                loc_ref if isinstance(loc_ref, dict) else None
            )

    service_type = resource.get("serviceType")
    if isinstance(service_type, dict):
        service_type_text, _ = _extract_coding(service_type)
        payload["department"] = service_type_text

    if reason_for_visit:
        payload["chief_complaint"] = reason_for_visit

    notes = _extract_note_text(resource)
    if notes:
        payload["clinical_notes"] = notes

    return payload


class LiveFHIRSyncAdapter:
    """Live sync adapter that pulls FHIR resources from provider endpoints."""

    def __init__(self, *, local_fallback_adapter: ProviderSyncAdapter) -> None:
        self._local_fallback_adapter = local_fallback_adapter

    async def sync(
        self,
        *,
        db: AsyncSession,
        connection: PatientDataConnection,
        now: datetime,
    ) -> ProviderSyncResult:
        config = _resolve_live_provider_config(connection)
        if config is None:
            if settings.provider_sync_live_fallback_to_local_scan:
                fallback_result = await self._local_fallback_adapter.sync(
                    db=db,
                    connection=connection,
                    now=now,
                )
                return ProviderSyncResult(
                    source_count_total=fallback_result.source_count_total,
                    source_count_delta=fallback_result.source_count_delta,
                    details=(
                        "live_fhir_not_configured; used_local_fallback; "
                        f"{fallback_result.details}"
                    ),
                )
            raise RuntimeError(
                "Live sync is enabled for provider but base URL is not configured"
            )
        try:
            patient_ref = await _resolve_patient_reference(
                db=db,
                connection=connection,
                config=config,
            )
            since = connection.last_synced_at

            observations = await _fetch_fhir_resources(
                config=config,
                resource_type="Observation",
                patient_ref=patient_ref,
                since=since,
            )
            medication_requests = await _fetch_fhir_resources(
                config=config,
                resource_type="MedicationRequest",
                patient_ref=patient_ref,
                since=since,
            )
            encounters = await _fetch_fhir_resources(
                config=config,
                resource_type="Encounter",
                patient_ref=patient_ref,
                since=since,
            )

            lab_service = LabIngestionService(db)
            medication_service = MedicationIngestionService(db)
            encounter_service = EncounterIngestionService(db)

            created_labs = 0
            created_meds = 0
            created_encounters = 0
            skipped_duplicates = 0
            parse_failures = 0

            for resource in observations:
                payload = _map_observation_to_lab_payload(
                    connection=connection,
                    resource=resource,
                )
                if payload is None:
                    parse_failures += 1
                    continue
                if await _record_exists_by_source(
                    db=db,
                    model=LabResult,
                    patient_id=connection.patient_id,
                    source_system=connection.provider_slug,
                    source_id=payload.get("source_id"),
                ):
                    skipped_duplicates += 1
                    continue
                try:
                    await lab_service.ingest_single(payload)
                    created_labs += 1
                except Exception as exc:
                    parse_failures += 1
                    logger.warning(
                        "Observation ingestion failed provider=%s source_id=%s: %s",
                        connection.provider_slug,
                        payload.get("source_id"),
                        exc,
                    )

            for resource in medication_requests:
                payload = _map_medication_request_to_payload(
                    connection=connection,
                    resource=resource,
                )
                if payload is None:
                    parse_failures += 1
                    continue
                if await _record_exists_by_source(
                    db=db,
                    model=Medication,
                    patient_id=connection.patient_id,
                    source_system=connection.provider_slug,
                    source_id=payload.get("source_id"),
                ):
                    skipped_duplicates += 1
                    continue
                try:
                    await medication_service.ingest_single(payload)
                    created_meds += 1
                except Exception as exc:
                    parse_failures += 1
                    logger.warning(
                        "MedicationRequest ingestion failed provider=%s source_id=%s: %s",
                        connection.provider_slug,
                        payload.get("source_id"),
                        exc,
                    )

            for resource in encounters:
                payload = _map_encounter_to_payload(
                    connection=connection,
                    resource=resource,
                )
                if payload is None:
                    parse_failures += 1
                    continue
                if await _record_exists_by_source(
                    db=db,
                    model=Encounter,
                    patient_id=connection.patient_id,
                    source_system=connection.provider_slug,
                    source_id=payload.get("source_id"),
                ):
                    skipped_duplicates += 1
                    continue
                try:
                    await encounter_service.ingest_single(payload)
                    created_encounters += 1
                except Exception as exc:
                    parse_failures += 1
                    logger.warning(
                        "Encounter ingestion failed provider=%s source_id=%s: %s",
                        connection.provider_slug,
                        payload.get("source_id"),
                        exc,
                    )

            delta = created_labs + created_meds + created_encounters
            total = await _count_records_for_source_system(
                db=db,
                patient_id=connection.patient_id,
                source_system=connection.provider_slug,
            )

            details_dict = {
                "mode": "live_fhir",
                "provider_key": config.provider_key,
                "fetched": {
                    "observations": len(observations),
                    "medication_requests": len(medication_requests),
                    "encounters": len(encounters),
                },
                "created": {
                    "labs": created_labs,
                    "medications": created_meds,
                    "encounters": created_encounters,
                },
                "skipped_duplicates": skipped_duplicates,
                "parse_failures": parse_failures,
            }
            details = json.dumps(details_dict, separators=(",", ":"))

            return ProviderSyncResult(
                source_count_total=total,
                source_count_delta=delta,
                details=details,
            )
        except Exception as exc:
            if not settings.provider_sync_live_fallback_to_local_scan:
                raise
            fallback_result = await self._local_fallback_adapter.sync(
                db=db,
                connection=connection,
                now=now,
            )
            details = json.dumps(
                {
                    "mode": "live_fhir_with_local_fallback",
                    "provider_key": config.provider_key,
                    "live_error": str(exc),
                    "fallback": {
                        "source_count_total": fallback_result.source_count_total,
                        "source_count_delta": fallback_result.source_count_delta,
                        "details": fallback_result.details,
                    },
                },
                separators=(",", ":"),
            )
            logger.warning(
                "Live FHIR sync failed for provider=%s; used local fallback: %s",
                connection.provider_slug,
                exc,
            )
            return ProviderSyncResult(
                source_count_total=fallback_result.source_count_total,
                source_count_delta=fallback_result.source_count_delta,
                details=details,
            )


async def validate_provider_sync_connection(
    *,
    db: AsyncSession,
    connection: PatientDataConnection,
) -> ProviderSyncValidationResult:
    """Validate live sync configuration and endpoint connectivity without ingesting."""
    config = _resolve_live_provider_config(connection)
    if config is None:
        if settings.provider_sync_live_fallback_to_local_scan:
            return ProviderSyncValidationResult(
                ok=True,
                mode="local_fallback",
                provider_key=connection.provider_slug,
                base_url=None,
                patient_ref=None,
                counts={},
                details=(
                    "Live provider endpoint is not configured; "
                    "sync will use local fallback adapter."
                ),
            )
        return ProviderSyncValidationResult(
            ok=False,
            mode="live_fhir",
            provider_key=connection.provider_slug,
            base_url=None,
            patient_ref=None,
            counts={},
            details=(
                "Live provider endpoint is not configured and fallback is disabled."
            ),
        )

    try:
        patient_ref = await _resolve_patient_reference(
            db=db,
            connection=connection,
            config=config,
        )
        counts = {
            "Observation": await _fetch_fhir_resource_count(
                config=config,
                resource_type="Observation",
                patient_ref=patient_ref,
            ),
            "MedicationRequest": await _fetch_fhir_resource_count(
                config=config,
                resource_type="MedicationRequest",
                patient_ref=patient_ref,
            ),
            "Encounter": await _fetch_fhir_resource_count(
                config=config,
                resource_type="Encounter",
                patient_ref=patient_ref,
            ),
        }
        return ProviderSyncValidationResult(
            ok=True,
            mode="live_fhir",
            provider_key=config.provider_key,
            base_url=config.base_url,
            patient_ref=patient_ref,
            counts=counts,
            details="Live provider connectivity check passed.",
        )
    except Exception as exc:
        if settings.provider_sync_live_fallback_to_local_scan:
            fallback_result = await _LOCAL_DELTA_ADAPTER.sync(
                db=db,
                connection=connection,
                now=datetime.now(UTC),
            )
            return ProviderSyncValidationResult(
                ok=True,
                mode="local_fallback",
                provider_key=config.provider_key,
                base_url=config.base_url,
                patient_ref=None,
                counts={},
                details=(
                    f"Live provider connectivity check failed: {exc}. "
                    "Falling back to local delta scan "
                    f"(total={fallback_result.source_count_total}, "
                    f"delta={fallback_result.source_count_delta})."
                ),
            )
        return ProviderSyncValidationResult(
            ok=False,
            mode="live_fhir",
            provider_key=config.provider_key,
            base_url=config.base_url,
            patient_ref=None,
            counts={},
            details=f"Live provider connectivity check failed: {exc}",
        )


_LOCAL_DELTA_ADAPTER = LocalDeltaScanAdapter()
_LIVE_FHIR_ADAPTER = LiveFHIRSyncAdapter(local_fallback_adapter=_LOCAL_DELTA_ADAPTER)

_ADAPTER_REGISTRY: dict[str, ProviderSyncAdapter] = {
    # Kenya interoperability stack: route to live FHIR adapter when configured.
    "digital_health_agency_dha": _LIVE_FHIR_ADAPTER,
    "national_shr_afyayangu": _LIVE_FHIR_ADAPTER,
    "kenya_health_information_system_khis": _LIVE_FHIR_ADAPTER,
    "integrated_health_information_system_ihis_hie": _LIVE_FHIR_ADAPTER,
    "moh_data_warehouse_dwh_dwapi": _LIVE_FHIR_ADAPTER,
    "afyarekod": _LIVE_FHIR_ADAPTER,
    "medbook_aphiaone_hmis": _LIVE_FHIR_ADAPTER,
    "ruphasoft": _LIVE_FHIR_ADAPTER,
    "ksatria_his": _LIVE_FHIR_ADAPTER,
    "dawascope": _LIVE_FHIR_ADAPTER,
    "kehmis_interoperability_layer": _LIVE_FHIR_ADAPTER,
    "shield_surveillance_linkage": _LIVE_FHIR_ADAPTER,
    "kemsa_lmis": _LIVE_FHIR_ADAPTER,
    "kenya_master_health_facility_list_kmhfl": _LIVE_FHIR_ADAPTER,
    "dha": _LIVE_FHIR_ADAPTER,
    "afyayangu": _LIVE_FHIR_ADAPTER,
    "khis": _LIVE_FHIR_ADAPTER,
    "ihis": _LIVE_FHIR_ADAPTER,
    "hie": _LIVE_FHIR_ADAPTER,
    "dwapi": _LIVE_FHIR_ADAPTER,
    "dwh": _LIVE_FHIR_ADAPTER,
    "kehmis": _LIVE_FHIR_ADAPTER,
    "shield": _LIVE_FHIR_ADAPTER,
    "kemsa": _LIVE_FHIR_ADAPTER,
    "kmhfl": _LIVE_FHIR_ADAPTER,
    "medbook": _LIVE_FHIR_ADAPTER,
    "aphiaone": _LIVE_FHIR_ADAPTER,
    "rupha": _LIVE_FHIR_ADAPTER,
    "ksatria": _LIVE_FHIR_ADAPTER,
}
_DEFAULT_ADAPTER: ProviderSyncAdapter = _LOCAL_DELTA_ADAPTER


def get_provider_sync_adapter(provider_slug: str) -> ProviderSyncAdapter:
    """Resolve provider sync adapter by slug with default fallback."""
    slug = (provider_slug or "").strip().lower()
    if not slug:
        return _DEFAULT_ADAPTER
    if slug in _ADAPTER_REGISTRY:
        return _ADAPTER_REGISTRY[slug]
    for key, adapter in _ADAPTER_REGISTRY.items():
        if key in slug:
            return adapter
    return _DEFAULT_ADAPTER
