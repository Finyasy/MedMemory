"""Dashboard API for connections, highlights, metric details, watchlists, and alerts."""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, delete, desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_authorized_patient
from app.config import settings
from app.database import get_db
from app.models import (
    FamilyHistory,
    LabResult,
    PatientConnectionSyncEvent,
    PatientDataConnection,
    PatientMetricAlert,
    PatientMetricDailySummary,
    PatientWatchMetric,
    User,
)
from app.schemas.dashboard import (
    AlertsEvaluateResponse,
    ConnectionSyncDryRunResponse,
    ConnectionSyncEventResponse,
    DashboardHighlightsResponse,
    DashboardSummary,
    DataConnectionResponse,
    DataConnectionUpsert,
    HighlightItem,
    MetricAlertResponse,
    MetricDetailResponse,
    MetricTrendPoint,
    WatchMetricCreate,
    WatchMetricResponse,
    WatchMetricUpdate,
)
from app.services.llm.evidence_validator import EvidenceValidator
from app.services.llm.model import LLMService
from app.services.provider_sync import validate_provider_sync_connection

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
logger = logging.getLogger(__name__)

_RANGE_PATTERN = re.compile(
    r"(?P<low>-?\d+(?:\.\d+)?)\s*[-–]\s*(?P<high>-?\d+(?:\.\d+)?)"
)

_KENYA_PROVIDER_CATALOG: dict[str, str] = {
    "digital_health_agency_dha": "Digital Health Agency (DHA)",
    "national_shr_afyayangu": "National Shared Health Record (SHR) / AfyaYangu",
    "kenya_health_information_system_khis": "Kenya Health Information System (KHIS)",
    "integrated_health_information_system_ihis_hie": "Integrated Health Information System (IHIS/HIE)",
    "moh_data_warehouse_dwh_dwapi": "MoH Data Warehouse (DWH / DWAPI)",
    "afyarekod": "AfyaRekod",
    "medbook_aphiaone_hmis": "Medbook (AphiaOne HMIS)",
    "ruphasoft": "RUPHAsoft",
    "ksatria_his": "Ksatria Hospital Information System",
    "dawascope": "Dawascope",
    "kehmis_interoperability_layer": "KeHMIS Interoperability Layer",
    "shield_surveillance_linkage": "SHIELD Surveillance Linkage",
    "kemsa_lmis": "KEMSA LMIS",
    "kenya_master_health_facility_list_kmhfl": "Kenya Master Health Facility List (KMHFL)",
}
_KENYA_PROVIDER_SLUGS = tuple(_KENYA_PROVIDER_CATALOG.keys())

_RISK_KEYWORD_TO_METRICS: dict[str, set[str]] = {
    "cardio": {
        "ldl_cholesterol",
        "hdl_cholesterol",
        "triglycerides",
        "apob",
        "lp_a",
        "blood_pressure",
        "systolic_blood_pressure",
        "diastolic_blood_pressure",
    },
    "heart": {
        "ldl_cholesterol",
        "hdl_cholesterol",
        "triglycerides",
        "apob",
        "lp_a",
        "blood_pressure",
    },
    "stroke": {"blood_pressure", "ldl_cholesterol", "apob", "lp_a"},
    "cholesterol": {"ldl_cholesterol", "hdl_cholesterol", "triglycerides", "apob"},
    "diabetes": {"hemoglobin_a1c", "hba1c", "glucose", "fasting_glucose", "insulin"},
    "thyroid": {"tsh", "free_t4", "t4", "t3"},
    "prostate": {"psa", "psa_free"},
    "kidney": {"creatinine", "egfr", "bun"},
}

_METRIC_ALIAS_GROUPS: dict[str, set[str]] = {
    "ldl_cholesterol": {
        "ldl",
        "ldl_c",
        "ldl_cholesterol",
        "low_density_lipoprotein",
        "low_density_lipoprotein_cholesterol",
    },
    "hdl_cholesterol": {
        "hdl",
        "hdl_c",
        "hdl_cholesterol",
        "high_density_lipoprotein",
        "high_density_lipoprotein_cholesterol",
    },
    "total_cholesterol": {"cholesterol", "total_cholesterol"},
    "triglycerides": {"triglycerides", "triglyceride"},
    "hba1c": {"hba1c", "hemoglobin_a1c", "glycated_hemoglobin", "a1c"},
    "blood_pressure": {"blood_pressure", "bp", "systolic_diastolic"},
    "systolic_blood_pressure": {"systolic_blood_pressure", "systolic_bp", "sbp"},
    "diastolic_blood_pressure": {"diastolic_blood_pressure", "diastolic_bp", "dbp"},
    "glucose": {"glucose", "fasting_glucose", "blood_glucose"},
    "hemoglobin": {"hemoglobin", "hgb"},
    "omega_3": {"omega_3", "omega3", "omega_3_index"},
}
_ALIAS_TO_CANONICAL_KEY = {
    alias: canonical
    for canonical, aliases in _METRIC_ALIAS_GROUPS.items()
    for alias in aliases
}

_DEFAULT_UNIT_BY_METRIC_FAMILY: dict[str, str] = {
    "cholesterol": "mg/dL",
    "triglycerides": "mg/dL",
    "glucose": "mg/dL",
    "hba1c": "%",
    "hemoglobin": "g/dL",
}
_METRIC_FAMILY_BY_KEY: dict[str, str] = {
    "ldl_cholesterol": "cholesterol",
    "hdl_cholesterol": "cholesterol",
    "total_cholesterol": "cholesterol",
    "apob": "cholesterol",
    "lp_a": "cholesterol",
    "triglycerides": "triglycerides",
    "glucose": "glucose",
    "fasting_glucose": "glucose",
    "hba1c": "hba1c",
    "hemoglobin_a1c": "hba1c",
    "hemoglobin": "hemoglobin",
}
_UNIT_TOKEN_TO_CANONICAL: dict[str, str] = {
    "mg/dl": "mg/dL",
    "mgdl": "mg/dL",
    "mmol/l": "mmol/L",
    "mmoll": "mmol/L",
    "g/dl": "g/dL",
    "gdl": "g/dL",
    "g/l": "g/L",
    "gl": "g/L",
    "%": "%",
    "percent": "%",
}
_METRIC_CONVERSION_FACTORS: dict[tuple[str, str, str], float] = {
    ("cholesterol", "mg/dl", "mmol/l"): 0.02586,
    ("cholesterol", "mmol/l", "mg/dl"): 38.67,
    ("triglycerides", "mg/dl", "mmol/l"): 0.01129,
    ("triglycerides", "mmol/l", "mg/dl"): 88.57,
    ("glucose", "mg/dl", "mmol/l"): 0.0555,
    ("glucose", "mmol/l", "mg/dl"): 18.0182,
    ("hemoglobin", "g/dl", "g/l"): 10.0,
    ("hemoglobin", "g/l", "g/dl"): 0.1,
}
_METRIC_ABOUT_REFUSAL = "I do not know from the available records."
_metric_evidence_validator = EvidenceValidator()


def canonical_metric_key(value: str) -> str:
    """Map metric names/aliases to a canonical key for cross-provider timelines."""
    normalized = normalize_metric_key(value)
    return _ALIAS_TO_CANONICAL_KEY.get(normalized, normalized)


def _metric_alias_keys(metric_key: str) -> set[str]:
    canonical = canonical_metric_key(metric_key)
    aliases = set(_METRIC_ALIAS_GROUPS.get(canonical, {canonical}))
    aliases.add(canonical)
    return aliases


def _normalize_unit_token(unit: str | None) -> str | None:
    if not unit:
        return None
    token = unit.strip().lower().replace(" ", "")
    token = token.replace("per", "/")
    token = token.replace("mgdl", "mg/dl")
    token = token.replace("mmoll", "mmol/l")
    token = token.replace("gdl", "g/dl")
    token = token.replace("gl", "g/l") if token in {"gl"} else token
    return token or None


def _canonical_unit_display(unit: str | None) -> str | None:
    token = _normalize_unit_token(unit)
    if not token:
        return unit
    return _UNIT_TOKEN_TO_CANONICAL.get(token, unit)


def _metric_family(metric_key: str) -> str | None:
    key = canonical_metric_key(metric_key)
    if key in _METRIC_FAMILY_BY_KEY:
        return _METRIC_FAMILY_BY_KEY[key]
    if "cholesterol" in key:
        return "cholesterol"
    if "triglyceride" in key:
        return "triglycerides"
    if "glucose" in key:
        return "glucose"
    return None


def _convert_metric_value(
    value: float | None,
    from_unit: str | None,
    to_unit: str | None,
    metric_key: str,
) -> float | None:
    if value is None:
        return None
    if not to_unit:
        return value
    if not from_unit:
        return None
    from_token = _normalize_unit_token(from_unit)
    to_token = _normalize_unit_token(to_unit)
    if not from_token or not to_token:
        return None
    if from_token == to_token:
        return value
    family = _metric_family(metric_key)
    if not family:
        return None
    factor = _METRIC_CONVERSION_FACTORS.get((family, from_token, to_token))
    if factor is None:
        return None
    return value * factor


def _preferred_normalized_unit(metric_key: str, labs: list[LabResult]) -> str | None:
    family = _metric_family(metric_key)
    default_unit = _DEFAULT_UNIT_BY_METRIC_FAMILY.get(family) if family else None
    numeric_units: list[str] = []
    for lab in labs:
        if _lab_numeric_value(lab) is None:
            continue
        unit = _canonical_unit_display(lab.unit)
        if unit:
            numeric_units.append(unit)
    if default_unit:
        for lab in labs:
            if _lab_numeric_value(lab) is None:
                continue
            converted = _convert_metric_value(
                _lab_numeric_value(lab),
                lab.unit,
                default_unit,
                metric_key,
            )
            if converted is not None:
                return default_unit
    if numeric_units:
        counts = Counter(numeric_units)
        return counts.most_common(1)[0][0]
    for lab in labs:
        if lab.unit:
            return _canonical_unit_display(lab.unit)
    return None


def _format_numeric(value: float | None) -> str | None:
    if value is None:
        return None
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _lab_provider_name(lab: LabResult) -> str | None:
    for value in (lab.performing_lab, lab.source_system, lab.ordering_provider):
        if value and value.strip():
            return value.strip()
    return None


def _lab_freshness_days(lab: LabResult) -> int | None:
    if lab.collected_at is None:
        return None
    delta = datetime.now(UTC) - lab.collected_at
    return max(int(delta.total_seconds() // 86400), 0)


def _lab_quality_score(lab: LabResult) -> float:
    score = 1.0
    numeric = _lab_numeric_value(lab)
    if numeric is None and not _lab_value_text(lab):
        score -= 0.4
    if not lab.unit:
        score -= 0.1
    if not lab.reference_range:
        score -= 0.1
    if lab.collected_at is None:
        score -= 0.2
    if not _lab_provider_name(lab):
        score -= 0.1
    return max(0.0, min(1.0, score))


def _freshness_score(days: int | None) -> float:
    if days is None:
        return 0.35
    if days <= 30:
        return 1.0
    if days <= 90:
        return 0.85
    if days <= 180:
        return 0.7
    if days <= 365:
        return 0.55
    return 0.4


def _confidence_label(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.6:
        return "medium"
    return "low"


def _lab_confidence(lab: LabResult) -> tuple[float, str, int | None]:
    freshness_days = _lab_freshness_days(lab)
    quality = _lab_quality_score(lab)
    score = max(0.0, min(1.0, (quality * 0.65) + (_freshness_score(freshness_days) * 0.35)))
    return score, _confidence_label(score), freshness_days


def _is_low_confidence(lab: LabResult) -> bool:
    score, _, _ = _lab_confidence(lab)
    return score < settings.dashboard_low_confidence_threshold


def normalize_metric_key(value: str) -> str:
    """Normalize free-form metric names into stable keys."""
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "unknown_metric"


def parse_reference_range(
    reference_range: str | None,
) -> tuple[float | None, float | None]:
    """Parse common numeric range formats like '70-100' or '70 – 100 mg/dL'."""
    if not reference_range:
        return None, None
    match = _RANGE_PATTERN.search(reference_range)
    if not match:
        return None, None
    try:
        return float(match.group("low")), float(match.group("high"))
    except (TypeError, ValueError):
        return None, None


def _lab_numeric_value(lab: LabResult) -> float | None:
    if lab.numeric_value is not None:
        return float(lab.numeric_value)
    if lab.value is None:
        return None
    try:
        return float(lab.value)
    except (TypeError, ValueError):
        return None


def _lab_value_text(lab: LabResult) -> str | None:
    if lab.value:
        return lab.value
    numeric = _lab_numeric_value(lab)
    if numeric is None:
        return None
    if float(numeric).is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}".rstrip("0").rstrip(".")


def _normalized_reference_bounds(
    lab: LabResult,
    metric_key: str,
    normalized_unit: str | None,
) -> tuple[float | None, float | None]:
    low, high = parse_reference_range(lab.reference_range)
    if normalized_unit is None:
        return low, high
    return (
        _convert_metric_value(low, lab.unit, normalized_unit, metric_key),
        _convert_metric_value(high, lab.unit, normalized_unit, metric_key),
    )


def _build_metric_trend_point(
    *,
    lab: LabResult,
    metric_key: str,
    normalized_unit: str | None,
) -> MetricTrendPoint:
    raw_numeric = _lab_numeric_value(lab)
    raw_text = _lab_value_text(lab)
    normalized_numeric = _convert_metric_value(
        raw_numeric,
        lab.unit,
        normalized_unit,
        metric_key,
    )
    if normalized_numeric is None:
        normalized_numeric = raw_numeric
    normalized_text = _format_numeric(normalized_numeric) or raw_text
    score, label, freshness_days = _lab_confidence(lab)
    excluded = score < settings.dashboard_low_confidence_threshold
    display_unit = normalized_unit or _canonical_unit_display(lab.unit)
    return MetricTrendPoint(
        value=normalized_numeric,
        value_text=normalized_text,
        raw_value=raw_numeric,
        raw_value_text=raw_text,
        raw_unit=_canonical_unit_display(lab.unit),
        normalized_value=normalized_numeric,
        normalized_value_text=normalized_text,
        normalized_unit=display_unit,
        observed_at=lab.collected_at,
        source_type="lab_result",
        source_id=lab.id,
        provider_name=_lab_provider_name(lab),
        confidence_score=score,
        confidence_label=label,
        freshness_days=freshness_days,
        excluded_from_insights=excluded,
        exclusion_reason=(
            "Low source confidence (quality/freshness) - excluded from automated insights."
            if excluded
            else None
        ),
    )


def _evaluate_lab_direction(lab: LabResult) -> str | None:
    numeric = _lab_numeric_value(lab)
    if numeric is None:
        return "abnormal" if lab.is_abnormal else None
    low, high = parse_reference_range(lab.reference_range)
    if low is not None and numeric < low:
        return "below"
    if high is not None and numeric > high:
        return "above"
    if lab.is_abnormal:
        return "abnormal"
    return "in_range"


def _metric_about_fallback_text(metric_name: str, unit: str | None) -> str:
    unit_text = f" ({unit})" if unit else ""
    return (
        f"{metric_name}{unit_text} is shown from your uploaded records. "
        "This view tracks the latest value, reference range, and trend over time."
    )


def _metric_about_context_lines(
    *,
    metric_key: str,
    labs: list[LabResult],
    normalized_unit: str | None,
    max_points: int = 8,
) -> str:
    lines: list[str] = []
    for lab in labs[: max(1, max_points)]:
        raw_numeric = _lab_numeric_value(lab)
        normalized_numeric = _convert_metric_value(
            raw_numeric,
            lab.unit,
            normalized_unit,
            metric_key,
        )
        if normalized_numeric is None:
            normalized_numeric = raw_numeric
        value_text = _format_numeric(normalized_numeric) or _lab_value_text(lab) or "not recorded"
        value_unit = normalized_unit or _canonical_unit_display(lab.unit) or ""
        value_display = f"{value_text} {value_unit}".strip()
        observed_at = lab.collected_at.date().isoformat() if lab.collected_at else "undated"
        source_ref = f"lab_result#{lab.id}" if lab.id is not None else "lab_result#unknown"
        reference_range = lab.reference_range or "not provided"
        lines.append(
            f"- {observed_at}: {lab.test_name} = {value_display}; "
            f"reference_range={reference_range}; source: {source_ref}"
        )
    return "\n".join(lines)


async def _metric_about_text(
    *,
    metric_name: str,
    metric_key: str,
    unit: str | None,
    labs: list[LabResult],
    normalized_unit: str | None,
) -> str:
    """Generate evidence-grounded metric explanation with deterministic fallback."""
    fallback_text = _metric_about_fallback_text(metric_name, unit)
    if not settings.dashboard_metric_about_rag_enabled:
        return fallback_text
    if not labs:
        return fallback_text

    context_lines = _metric_about_context_lines(
        metric_key=metric_key,
        labs=labs,
        normalized_unit=normalized_unit,
    )
    if not context_lines.strip():
        return fallback_text
    if len(context_lines) > settings.dashboard_metric_about_context_chars:
        context_lines = context_lines[: settings.dashboard_metric_about_context_chars]

    prompt = (
        "Write a short 'About this metric' explanation for a patient dashboard.\n"
        "Use ONLY values in METRIC_RECORD_CONTEXT.\n"
        "If information is missing, return exactly: "
        f"{_METRIC_ABOUT_REFUSAL}\n"
        "Rules:\n"
        "- Keep to 1-2 concise sentences.\n"
        "- Every sentence containing numbers must include inline citation: "
        "(source: lab_result#ID).\n"
        "- No diagnosis, no treatment advice, no extra headings.\n\n"
        f"Metric: {metric_name}\n"
        "METRIC_RECORD_CONTEXT:\n"
        f"{context_lines}\n"
    )
    try:
        llm_response = await LLMService.get_instance().generate(
            prompt=prompt,
            max_new_tokens=140,
            do_sample=False,
            temperature=0.0,
            top_p=1.0,
            top_k=40,
        )
    except Exception:
        logger.exception("Failed to generate RAG-grounded metric explanation")
        return fallback_text

    candidate = (llm_response.text or "").strip()
    if not candidate:
        return fallback_text

    grounded_text, _ = _metric_evidence_validator.enforce_numeric_grounding(
        response=candidate,
        context_text=context_lines,
        refusal_message=_METRIC_ABOUT_REFUSAL,
    )
    cited_text, _ = _metric_evidence_validator.enforce_numeric_citations(
        response=grounded_text,
        refusal_message=_METRIC_ABOUT_REFUSAL,
    )
    cleaned = cited_text.strip()
    if not cleaned or cleaned == _METRIC_ABOUT_REFUSAL:
        return fallback_text
    return cleaned


def _metric_risk_overlay(
    metric_key: str, family_history: list[FamilyHistory]
) -> tuple[float, str | None]:
    normalized_key = metric_key.lower()
    best_reason: str | None = None
    best_score = 0.0
    for item in family_history:
        condition = (item.condition or "").lower()
        relation = (item.relation or "").strip().lower()
        if not condition:
            continue
        for keyword, target_metrics in _RISK_KEYWORD_TO_METRICS.items():
            if keyword not in condition:
                continue
            if normalized_key not in target_metrics:
                continue
            score = 1.0
            if relation in {"mother", "father", "brother", "sister"}:
                score += 0.5
            if item.age_of_onset is not None and item.age_of_onset < 60:
                score += 0.5
            if score > best_score:
                best_score = score
                reason = f"Prioritized due to family history of {item.condition}"
                if item.relation:
                    reason += f" ({item.relation})"
                best_reason = reason
    return best_score, best_reason


def _trend_change_delta(
    latest: LabResult,
    previous: LabResult | None,
) -> tuple[float | None, bool]:
    latest_numeric = _lab_numeric_value(latest)
    previous_numeric = _lab_numeric_value(previous) if previous else None
    if latest_numeric is None or previous_numeric is None:
        return None, False
    delta = latest_numeric - previous_numeric
    if previous_numeric == 0:
        return delta, abs(delta) >= 1.0
    percent_delta = abs(delta) / abs(previous_numeric)
    return delta, percent_delta >= 0.20


def _connection_event_type(
    *,
    status_before: str | None,
    status_after: str,
    is_active_after: bool,
    last_error: str | None,
    created: bool,
) -> str:
    if created:
        return "connected" if is_active_after else "disconnected"
    if status_after == "syncing":
        return "sync_started"
    if status_after == "error" or last_error:
        return "sync_failed"
    if not is_active_after or status_after == "disconnected":
        return "disconnected"
    if status_before == "syncing" and status_after == "connected":
        return "sync_completed"
    if status_before != status_after:
        return "updated"
    return "updated"


def _daily_summary_date(now_utc: datetime | None = None) -> date:
    current = now_utc or datetime.now(UTC)
    return current.date()


async def _load_daily_summary_rows(
    *,
    patient_id: int,
    db: AsyncSession,
    summary_date: date | None = None,
) -> tuple[date | None, list[PatientMetricDailySummary]]:
    """Load metric daily summary rows for a date or latest available date."""
    target_date = summary_date
    if target_date is None:
        target_date = await db.scalar(
            select(func.max(PatientMetricDailySummary.summary_date)).where(
                PatientMetricDailySummary.patient_id == patient_id
            )
        )
    if target_date is None:
        return None, []

    rows = await db.execute(
        select(PatientMetricDailySummary)
        .where(
            and_(
                PatientMetricDailySummary.patient_id == patient_id,
                PatientMetricDailySummary.summary_date == target_date,
            )
        )
        .order_by(PatientMetricDailySummary.observed_at.desc().nullslast())
    )
    return target_date, list(rows.scalars().all())


def _build_daily_summary_payload(
    *,
    patient_id: int,
    summary_date: date,
    labs: list[LabResult],
) -> tuple[list[dict], datetime | None]:
    """Build upsert payload for patient metric daily summaries."""
    grouped_labs: dict[str, list[LabResult]] = {}
    latest_by_metric: dict[str, LabResult] = {}
    previous_by_metric: dict[str, LabResult] = {}
    last_updated_at: datetime | None = None

    for lab in labs:
        metric_key = canonical_metric_key(lab.test_name)
        grouped_labs.setdefault(metric_key, []).append(lab)
        if metric_key not in latest_by_metric:
            latest_by_metric[metric_key] = lab
        elif metric_key not in previous_by_metric:
            previous_by_metric[metric_key] = lab

    payload: list[dict] = []
    for metric_key, latest in latest_by_metric.items():
        latest_numeric_raw = _lab_numeric_value(latest)
        latest_value_text = _lab_value_text(latest)
        metric_labs = grouped_labs.get(metric_key, [latest])
        normalized_unit = _preferred_normalized_unit(metric_key, metric_labs)
        normalized_numeric = _convert_metric_value(
            latest_numeric_raw,
            latest.unit,
            normalized_unit,
            metric_key,
        )
        if normalized_numeric is None:
            normalized_numeric = latest_numeric_raw

        previous = previous_by_metric.get(metric_key)
        previous_numeric = _lab_numeric_value(previous) if previous is not None else None
        previous_normalized = _convert_metric_value(
            previous_numeric,
            previous.unit if previous is not None else None,
            normalized_unit,
            metric_key,
        )
        if previous_normalized is None:
            previous_normalized = previous_numeric
        trend_delta = (
            normalized_numeric - previous_normalized
            if normalized_numeric is not None and previous_normalized is not None
            else None
        )

        confidence_score, confidence_label, freshness_days = _lab_confidence(latest)
        payload.append(
            {
                "patient_id": patient_id,
                "summary_date": summary_date,
                "metric_key": metric_key,
                "metric_name": latest.test_name,
                "value_text": latest_value_text,
                "numeric_value": latest_numeric_raw,
                "unit": _canonical_unit_display(latest.unit),
                "normalized_value": normalized_numeric,
                "normalized_unit": normalized_unit or _canonical_unit_display(latest.unit),
                "status": "out_of_range" if latest.is_abnormal else "in_range",
                "direction": _evaluate_lab_direction(latest),
                "trend_delta": trend_delta,
                "observed_at": latest.collected_at,
                "source_type": "lab_result",
                "source_id": latest.id,
                "provider_name": _lab_provider_name(latest),
                "confidence_score": confidence_score,
                "confidence_label": confidence_label,
                "freshness_days": freshness_days,
                "excluded_from_insights": confidence_score
                < settings.dashboard_low_confidence_threshold,
            }
        )
        if latest.collected_at is not None and (
            last_updated_at is None or latest.collected_at > last_updated_at
        ):
            last_updated_at = latest.collected_at

    return payload, last_updated_at


async def refresh_patient_metric_daily_summary(
    *,
    patient_id: int,
    db: AsyncSession,
    summary_date: date | None = None,
) -> tuple[int, datetime | None]:
    """Refresh persisted daily metric summaries for a patient."""
    target_date = summary_date or _daily_summary_date()
    rows = await db.execute(
        select(LabResult)
        .where(LabResult.patient_id == patient_id)
        .order_by(LabResult.collected_at.desc().nullslast(), LabResult.id.desc())
        .limit(800)
    )
    labs = list(rows.scalars().all())
    if not labs:
        await db.execute(
            delete(PatientMetricDailySummary).where(
                and_(
                    PatientMetricDailySummary.patient_id == patient_id,
                    PatientMetricDailySummary.summary_date == target_date,
                )
            )
        )
        await db.flush()
        return 0, None

    payload, last_updated_at = _build_daily_summary_payload(
        patient_id=patient_id,
        summary_date=target_date,
        labs=labs,
    )
    if payload:
        stmt = insert(PatientMetricDailySummary).values(payload)
        await db.execute(
            stmt.on_conflict_do_update(
                constraint="uq_metric_daily_summary_patient_date_metric",
                set_={
                    "metric_name": stmt.excluded.metric_name,
                    "value_text": stmt.excluded.value_text,
                    "numeric_value": stmt.excluded.numeric_value,
                    "unit": stmt.excluded.unit,
                    "normalized_value": stmt.excluded.normalized_value,
                    "normalized_unit": stmt.excluded.normalized_unit,
                    "status": stmt.excluded.status,
                    "direction": stmt.excluded.direction,
                    "trend_delta": stmt.excluded.trend_delta,
                    "observed_at": stmt.excluded.observed_at,
                    "source_type": stmt.excluded.source_type,
                    "source_id": stmt.excluded.source_id,
                    "provider_name": stmt.excluded.provider_name,
                    "confidence_score": stmt.excluded.confidence_score,
                    "confidence_label": stmt.excluded.confidence_label,
                    "freshness_days": stmt.excluded.freshness_days,
                    "excluded_from_insights": stmt.excluded.excluded_from_insights,
                    "updated_at": func.now(),
                },
            )
        )
        metric_keys = [row["metric_key"] for row in payload]
        await db.execute(
            delete(PatientMetricDailySummary).where(
                and_(
                    PatientMetricDailySummary.patient_id == patient_id,
                    PatientMetricDailySummary.summary_date == target_date,
                    PatientMetricDailySummary.metric_key.notin_(metric_keys),
                )
            )
        )
    else:
        await db.execute(
            delete(PatientMetricDailySummary).where(
                and_(
                    PatientMetricDailySummary.patient_id == patient_id,
                    PatientMetricDailySummary.summary_date == target_date,
                )
            )
        )
    await db.flush()
    return len(payload), last_updated_at


async def _summary_needs_refresh(
    *,
    patient_id: int,
    db: AsyncSession,
    summary_date: date,
    summary_rows: list[PatientMetricDailySummary],
) -> bool:
    """Return True when persisted summary is missing or stale vs newest lab."""
    if not summary_rows:
        return True
    summary_latest = max(
        (
            row.observed_at
            for row in summary_rows
            if row.observed_at is not None and row.summary_date == summary_date
        ),
        default=None,
    )
    newest_lab = await db.scalar(
        select(func.max(LabResult.collected_at)).where(LabResult.patient_id == patient_id)
    )
    if newest_lab is None:
        return False
    if summary_latest is None:
        return True
    return newest_lab > summary_latest


async def _load_lab_reference_ranges(
    *,
    db: AsyncSession,
    source_ids: list[int],
) -> dict[int, str | None]:
    if not source_ids:
        return {}
    rows = await db.execute(
        select(LabResult.id, LabResult.reference_range).where(LabResult.id.in_(source_ids))
    )
    return {int(lab_id): reference_range for lab_id, reference_range in rows.all()}


def _summary_row_to_highlight(
    *,
    row: PatientMetricDailySummary,
    risk_priority_score: float,
    risk_priority_reason: str | None,
    reference_range: str | None,
) -> HighlightItem:
    return HighlightItem(
        metric_key=row.metric_key,
        metric_name=row.metric_name,
        value=row.value_text,
        numeric_value=row.numeric_value,
        unit=row.unit,
        observed_at=row.observed_at,
        status=row.status,
        direction=row.direction,
        trend_delta=row.trend_delta,
        reference_range=reference_range,
        risk_priority_score=risk_priority_score,
        risk_priority_reason=risk_priority_reason,
        source_type=row.source_type,
        source_id=row.source_id,
        provider_name=row.provider_name,
        confidence_score=row.confidence_score,
        confidence_label=row.confidence_label,
        freshness_days=row.freshness_days,
    )


def _sort_highlights_for_dashboard(highlights: list[HighlightItem]) -> list[HighlightItem]:
    return sorted(
        highlights,
        key=lambda h: (
            0 if h.status == "out_of_range" else 1,
            -float(h.risk_priority_score or 0.0),
            -abs(float(h.trend_delta or 0.0)),
            -(h.observed_at.timestamp() if h.observed_at else 0.0),
        ),
    )


@router.get(
    "/patient/{patient_id}/connections",
    response_model=list[DataConnectionResponse],
)
async def list_data_connections(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List data-source connections and current sync state for a patient."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    result = await db.execute(
        select(PatientDataConnection)
        .where(
            and_(
                PatientDataConnection.patient_id == patient_id,
                PatientDataConnection.provider_slug.in_(_KENYA_PROVIDER_SLUGS),
            )
        )
        .order_by(
            PatientDataConnection.provider_name.asc(),
            PatientDataConnection.id.asc(),
        )
    )
    return list(result.scalars().all())


@router.get(
    "/patient/{patient_id}/connections/events",
    response_model=list[ConnectionSyncEventResponse],
)
async def list_connection_sync_events(
    patient_id: int,
    provider_slug: str | None = None,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List connection and sync audit events for trust/debug visibility."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    limit = max(1, min(limit, 200))
    filters = [
        PatientConnectionSyncEvent.patient_id == patient_id,
        PatientConnectionSyncEvent.provider_slug.in_(_KENYA_PROVIDER_SLUGS),
    ]
    if provider_slug:
        filters.append(PatientConnectionSyncEvent.provider_slug == provider_slug)
    result = await db.execute(
        select(PatientConnectionSyncEvent)
        .where(*filters)
        .order_by(PatientConnectionSyncEvent.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.post(
    "/patient/{patient_id}/connections",
    response_model=DataConnectionResponse,
)
async def upsert_data_connection(
    patient_id: int,
    payload: DataConnectionUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Create or update a provider connection row for the patient."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    if payload.provider_slug not in _KENYA_PROVIDER_CATALOG:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Unsupported provider_slug. "
                "Only Kenya data-source catalog providers are allowed."
            ),
        )
    canonical_provider_name = _KENYA_PROVIDER_CATALOG[payload.provider_slug]
    existing_result = await db.execute(
        select(PatientDataConnection).where(
            and_(
                PatientDataConnection.patient_id == patient_id,
                PatientDataConnection.provider_slug == payload.provider_slug,
            )
        )
    )
    connection = existing_result.scalar_one_or_none()
    created = connection is None
    status_before = connection.status if connection is not None else None
    if connection is None:
        connection = PatientDataConnection(
            patient_id=patient_id,
            provider_name=canonical_provider_name,
            provider_slug=payload.provider_slug,
        )
        db.add(connection)
    connection.provider_name = canonical_provider_name
    connection.status = payload.status
    connection.source_count = payload.source_count
    connection.last_error = payload.last_error
    connection.last_synced_at = payload.last_synced_at
    connection.is_active = payload.is_active
    await db.flush()

    event_type = _connection_event_type(
        status_before=status_before,
        status_after=connection.status,
        is_active_after=connection.is_active,
        last_error=connection.last_error,
        created=created,
    )
    if created or status_before != connection.status or payload.last_error:
        db.add(
            PatientConnectionSyncEvent(
                patient_id=patient_id,
                connection_id=connection.id,
                provider_slug=connection.provider_slug,
                event_type=event_type,
                status_before=status_before,
                status_after=connection.status,
                details=(
                    "Connection created"
                    if created
                    else f"Connection updated to status {connection.status}"
                ),
                last_error=connection.last_error,
                triggered_by_user_id=current_user.id,
            )
        )
        await db.flush()

    await db.refresh(connection)
    return connection


@router.post(
    "/patient/{patient_id}/connections/{connection_id}/sync",
    response_model=DataConnectionResponse,
)
async def mark_connection_synced(
    patient_id: int,
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Mark a provider as recently synced."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    result = await db.execute(
        select(PatientDataConnection).where(
            and_(
                PatientDataConnection.id == connection_id,
                PatientDataConnection.patient_id == patient_id,
            )
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    status_before = connection.status
    connection.status = "connected"
    connection.last_error = None
    connection.last_synced_at = datetime.now(UTC)
    await db.flush()
    db.add(
        PatientConnectionSyncEvent(
            patient_id=patient_id,
            connection_id=connection.id,
            provider_slug=connection.provider_slug,
            event_type="sync_completed",
            status_before=status_before,
            status_after=connection.status,
            details="Manual sync completed",
            last_error=None,
            triggered_by_user_id=current_user.id,
        )
    )
    await db.flush()
    try:
        await refresh_patient_metric_daily_summary(patient_id=patient_id, db=db)
        await evaluate_metric_alerts_for_patient(patient_id=patient_id, db=db)
    except Exception:
        logger.exception(
            "Post-sync dashboard recompute failed for patient %s connection %s",
            patient_id,
            connection.id,
        )
    await db.refresh(connection)
    return connection


@router.post(
    "/patient/{patient_id}/connections/{connection_id}/sync/dry-run",
    response_model=ConnectionSyncDryRunResponse,
)
async def dry_run_connection_sync(
    patient_id: int,
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Validate provider live-sync configuration/connectivity without ingesting data."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    result = await db.execute(
        select(PatientDataConnection).where(
            and_(
                PatientDataConnection.id == connection_id,
                PatientDataConnection.patient_id == patient_id,
            )
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    validation = await validate_provider_sync_connection(
        db=db,
        connection=connection,
    )
    db.add(
        PatientConnectionSyncEvent(
            patient_id=patient_id,
            connection_id=connection.id,
            provider_slug=connection.provider_slug,
            event_type="updated",
            status_before=connection.status,
            status_after=connection.status,
            details=f"Manual sync dry-run: {validation.details}",
            last_error=None if validation.ok else validation.details[:500],
            triggered_by_user_id=current_user.id,
        )
    )
    await db.flush()
    return ConnectionSyncDryRunResponse(
        ok=validation.ok,
        mode=validation.mode,
        provider_key=validation.provider_key,
        base_url=validation.base_url,
        patient_ref=validation.patient_ref,
        counts=validation.counts,
        details=validation.details,
        checked_at=datetime.now(UTC),
    )


@router.get(
    "/patient/{patient_id}/highlights",
    response_model=DashboardHighlightsResponse,
)
async def get_dashboard_highlights(
    patient_id: int,
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Return a compact highlights set for dashboard cards."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    summary_date = _daily_summary_date()
    loaded_summary_date, summary_rows = await _load_daily_summary_rows(
        patient_id=patient_id,
        db=db,
        summary_date=summary_date,
    )
    if await _summary_needs_refresh(
        patient_id=patient_id,
        db=db,
        summary_date=summary_date,
        summary_rows=summary_rows,
    ):
        await refresh_patient_metric_daily_summary(
            patient_id=patient_id,
            db=db,
            summary_date=summary_date,
        )
        loaded_summary_date, summary_rows = await _load_daily_summary_rows(
            patient_id=patient_id,
            db=db,
            summary_date=summary_date,
        )
    if loaded_summary_date is None:
        _, summary_rows = await _load_daily_summary_rows(
            patient_id=patient_id,
            db=db,
            summary_date=None,
        )

    if not summary_rows:
        return DashboardHighlightsResponse(
            patient_id=patient_id,
            summary=DashboardSummary(
                out_of_range=0,
                in_range=0,
                tracked_metrics=0,
                last_updated_at=None,
            ),
            highlights=[],
        )

    family_history_rows = await db.execute(
        select(FamilyHistory)
        .where(FamilyHistory.patient_id == patient_id)
        .order_by(FamilyHistory.created_at.desc())
    )
    family_history = list(family_history_rows.scalars().all())
    source_ids = [
        int(row.source_id)
        for row in summary_rows
        if row.source_type == "lab_result" and row.source_id is not None
    ]
    reference_ranges = await _load_lab_reference_ranges(db=db, source_ids=source_ids)

    highlights: list[HighlightItem] = []
    for row in summary_rows:
        if row.excluded_from_insights:
            continue
        risk_priority_score, risk_priority_reason = _metric_risk_overlay(
            row.metric_key,
            family_history,
        )
        highlights.append(
            _summary_row_to_highlight(
                row=row,
                risk_priority_score=risk_priority_score,
                risk_priority_reason=risk_priority_reason,
                reference_range=reference_ranges.get(int(row.source_id))
                if row.source_id is not None
                else None,
            )
        )

    highlights = _sort_highlights_for_dashboard(highlights)
    out_of_range = sum(1 for item in highlights if item.status == "out_of_range")
    in_range = sum(1 for item in highlights if item.status == "in_range")
    last_updated_at = max(
        (item.observed_at for item in highlights if item.observed_at is not None),
        default=None,
    )

    return DashboardHighlightsResponse(
        patient_id=patient_id,
        summary=DashboardSummary(
            out_of_range=out_of_range,
            in_range=in_range,
            tracked_metrics=len(highlights),
            last_updated_at=last_updated_at,
        ),
        highlights=highlights[: max(1, min(limit, 12))],
    )


@router.get(
    "/patient/{patient_id}/metrics/{metric_key}",
    response_model=MetricDetailResponse,
)
async def get_metric_detail(
    patient_id: int,
    metric_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Return metric detail card data (latest value, range, and trend)."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    requested_key = canonical_metric_key(metric_key)
    aliases = _metric_alias_keys(requested_key)
    rows = await db.execute(
        select(LabResult)
        .where(LabResult.patient_id == patient_id)
        .order_by(LabResult.collected_at.desc().nullslast(), LabResult.id.desc())
        .limit(600)
    )
    all_labs = list(rows.scalars().all())
    labs = [
        lab
        for lab in all_labs
        if canonical_metric_key(lab.test_name) in aliases
    ]
    if not labs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metric not found for this patient",
        )
    latest = labs[0]
    normalized_unit = _preferred_normalized_unit(requested_key, labs)
    low, high = _normalized_reference_bounds(
        latest,
        metric_key=requested_key,
        normalized_unit=normalized_unit,
    )
    latest_numeric_raw = _lab_numeric_value(latest)
    latest_numeric = _convert_metric_value(
        latest_numeric_raw,
        latest.unit,
        normalized_unit,
        requested_key,
    )
    if latest_numeric is None:
        latest_numeric = latest_numeric_raw
    latest_normalized_text = _format_numeric(latest_numeric) or _lab_value_text(latest)
    latest_confidence_score, latest_confidence_label, latest_freshness_days = _lab_confidence(
        latest
    )
    display_unit = normalized_unit or _canonical_unit_display(latest.unit)
    in_range = None
    if latest_numeric is not None and low is not None and high is not None:
        in_range = low <= latest_numeric <= high
    trend = [
        _build_metric_trend_point(
            lab=lab,
            metric_key=requested_key,
            normalized_unit=normalized_unit,
        )
        for lab in reversed(labs[:24])
    ]
    excluded_points_count = sum(1 for point in trend if point.excluded_from_insights)
    normalization_applied = any(
        (
            point.raw_unit
            and point.normalized_unit
            and _normalize_unit_token(point.raw_unit)
            != _normalize_unit_token(point.normalized_unit)
        )
        for point in trend
    )
    about_text = await _metric_about_text(
        metric_name=latest.test_name,
        metric_key=requested_key,
        unit=display_unit,
        labs=labs,
        normalized_unit=normalized_unit,
    )
    return MetricDetailResponse(
        patient_id=patient_id,
        metric_key=requested_key,
        metric_name=latest.test_name,
        latest_value=_lab_value_text(latest),
        latest_numeric_value=latest_numeric,
        unit=display_unit,
        observed_at=latest.collected_at,
        reference_range=latest.reference_range,
        range_min=low,
        range_max=high,
        in_range=in_range,
        about=about_text,
        latest_source_type="lab_result",
        latest_source_id=latest.id,
        normalized_unit=display_unit,
        latest_normalized_value=latest_numeric,
        latest_normalized_value_text=latest_normalized_text,
        normalization_applied=normalization_applied,
        latest_confidence_score=latest_confidence_score,
        latest_confidence_label=latest_confidence_label,
        latest_freshness_days=latest_freshness_days,
        excluded_points_count=excluded_points_count,
        trend=trend,
    )


@router.get(
    "/patient/{patient_id}/watchlist",
    response_model=list[WatchMetricResponse],
)
async def list_watch_metrics(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List watchlist metrics for a patient."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    result = await db.execute(
        select(PatientWatchMetric)
        .where(PatientWatchMetric.patient_id == patient_id)
        .order_by(PatientWatchMetric.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/patient/{patient_id}/watchlist",
    response_model=WatchMetricResponse,
)
async def create_watch_metric(
    patient_id: int,
    payload: WatchMetricCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Create or update watchlist metric by metric key."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    metric_key = canonical_metric_key(payload.metric_key or payload.metric_name)
    existing = await db.execute(
        select(PatientWatchMetric).where(
            and_(
                PatientWatchMetric.patient_id == patient_id,
                PatientWatchMetric.metric_key == metric_key,
            )
        )
    )
    watch = existing.scalar_one_or_none()
    if watch is None:
        watch = PatientWatchMetric(
            patient_id=patient_id,
            metric_key=metric_key,
            metric_name=payload.metric_name,
        )
        db.add(watch)
    watch.metric_name = payload.metric_name
    watch.metric_key = metric_key
    watch.lower_bound = payload.lower_bound
    watch.upper_bound = payload.upper_bound
    watch.direction = payload.direction
    watch.is_active = payload.is_active
    await db.flush()
    await db.refresh(watch)
    return watch


@router.patch(
    "/patient/{patient_id}/watchlist/{watch_metric_id}",
    response_model=WatchMetricResponse,
)
async def update_watch_metric(
    patient_id: int,
    watch_metric_id: int,
    payload: WatchMetricUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update watchlist metric thresholds and status."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    result = await db.execute(
        select(PatientWatchMetric).where(
            and_(
                PatientWatchMetric.id == watch_metric_id,
                PatientWatchMetric.patient_id == patient_id,
            )
        )
    )
    watch = result.scalar_one_or_none()
    if watch is None:
        raise HTTPException(status_code=404, detail="Watch metric not found")
    patch = payload.model_dump(exclude_unset=True)
    if "metric_key" in patch and patch["metric_key"] is not None:
        patch["metric_key"] = canonical_metric_key(patch["metric_key"])
    if "metric_name" in patch and patch["metric_name"] is not None:
        patch.setdefault("metric_key", canonical_metric_key(patch["metric_name"]))
    for key, value in patch.items():
        setattr(watch, key, value)
    await db.flush()
    await db.refresh(watch)
    return watch


@router.delete(
    "/patient/{patient_id}/watchlist/{watch_metric_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_watch_metric(
    patient_id: int,
    watch_metric_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete a watchlist metric."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    result = await db.execute(
        select(PatientWatchMetric).where(
            and_(
                PatientWatchMetric.id == watch_metric_id,
                PatientWatchMetric.patient_id == patient_id,
            )
        )
    )
    watch = result.scalar_one_or_none()
    if watch is None:
        raise HTTPException(status_code=404, detail="Watch metric not found")
    await db.delete(watch)


@router.get(
    "/patient/{patient_id}/alerts",
    response_model=list[MetricAlertResponse],
)
async def list_metric_alerts(
    patient_id: int,
    include_acknowledged: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List generated metric alerts for a patient."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    filters = [PatientMetricAlert.patient_id == patient_id]
    if not include_acknowledged:
        filters.append(PatientMetricAlert.acknowledged.is_(False))
    result = await db.execute(
        select(PatientMetricAlert)
        .where(*filters)
        .order_by(desc(PatientMetricAlert.observed_at), desc(PatientMetricAlert.id))
        .limit(200)
    )
    return list(result.scalars().all())


def _watch_trigger_reason(
    watch: PatientWatchMetric,
    latest: LabResult,
    previous: LabResult | None,
) -> tuple[bool, str, str, float | None]:
    numeric = _lab_numeric_value(latest)
    if numeric is None:
        return False, "", "threshold", None
    trend_delta, has_sharp_change = _trend_change_delta(latest, previous)
    if (
        watch.direction in {"both", "above"}
        and watch.upper_bound is not None
        and numeric > watch.upper_bound
    ):
        return (
            True,
            f"value {numeric:g} is above watch upper bound {watch.upper_bound:g}",
            "threshold",
            trend_delta,
        )
    if (
        watch.direction in {"both", "below"}
        and watch.lower_bound is not None
        and numeric < watch.lower_bound
    ):
        return (
            True,
            f"value {numeric:g} is below watch lower bound {watch.lower_bound:g}",
            "threshold",
            trend_delta,
        )
    if watch.lower_bound is None and watch.upper_bound is None and latest.is_abnormal:
        return (
            True,
            "latest value flagged abnormal by source range",
            "abnormal",
            trend_delta,
        )
    if has_sharp_change and trend_delta is not None:
        prev_numeric = _lab_numeric_value(previous) if previous is not None else None
        percent = (
            (abs(trend_delta) / abs(prev_numeric)) * 100.0
            if prev_numeric not in (None, 0)
            else None
        )
        delta_text = (
            f"{percent:.1f}%" if percent is not None else f"{abs(trend_delta):g}"
        )
        direction = "up" if trend_delta > 0 else "down"
        return (
            True,
            f"value shifted {direction} by {delta_text} since prior result",
            "trend_change",
            trend_delta,
        )
    return False, "", "threshold", trend_delta


async def evaluate_metric_alerts_for_patient(
    *,
    patient_id: int,
    db: AsyncSession,
) -> AlertsEvaluateResponse:
    """Evaluate watchlist metrics for a patient and create deduplicated alerts."""
    watch_rows = await db.execute(
        select(PatientWatchMetric).where(
            PatientWatchMetric.patient_id == patient_id,
            PatientWatchMetric.is_active.is_(True),
        )
    )
    watches = list(watch_rows.scalars().all())
    if not watches:
        active_count = await db.scalar(
            select(func.count())
            .select_from(PatientMetricAlert)
            .where(
                PatientMetricAlert.patient_id == patient_id,
                PatientMetricAlert.acknowledged.is_(False),
            )
        )
        return AlertsEvaluateResponse(
            generated=0,
            total_active_unacknowledged=int(active_count or 0),
        )

    lab_rows = await db.execute(
        select(LabResult)
        .where(LabResult.patient_id == patient_id)
        .order_by(LabResult.collected_at.desc().nullslast(), LabResult.id.desc())
        .limit(400)
    )
    labs = list(lab_rows.scalars().all())
    latest_by_key: dict[str, LabResult] = {}
    previous_by_key: dict[str, LabResult] = {}
    for lab in labs:
        key = canonical_metric_key(lab.test_name)
        if key not in latest_by_key:
            latest_by_key[key] = lab
            continue
        if key not in previous_by_key:
            previous_by_key[key] = lab

    generated = 0
    for watch in watches:
        watch_key = canonical_metric_key(watch.metric_key)
        latest_lab = latest_by_key.get(watch_key)
        if latest_lab is None:
            continue
        if _is_low_confidence(latest_lab):
            continue
        previous_lab = previous_by_key.get(watch_key)
        should_alert, reason, alert_kind, trend_delta = _watch_trigger_reason(
            watch,
            latest_lab,
            previous_lab,
        )
        if not should_alert:
            continue
        existing = await db.execute(
            select(PatientMetricAlert).where(
                and_(
                    PatientMetricAlert.patient_id == patient_id,
                    PatientMetricAlert.watch_metric_id == watch.id,
                    PatientMetricAlert.source_type == "lab_result",
                    PatientMetricAlert.source_id == latest_lab.id,
                    PatientMetricAlert.reason == reason,
                    PatientMetricAlert.alert_kind == alert_kind,
                    PatientMetricAlert.acknowledged.is_(False),
                )
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        alert = PatientMetricAlert(
            patient_id=patient_id,
            watch_metric_id=watch.id,
            metric_key=watch.metric_key,
            metric_name=watch.metric_name,
            numeric_value=_lab_numeric_value(latest_lab),
            value_text=_lab_value_text(latest_lab),
            previous_numeric_value=(
                _lab_numeric_value(previous_lab) if previous_lab is not None else None
            ),
            previous_value_text=(
                _lab_value_text(previous_lab) if previous_lab is not None else None
            ),
            unit=latest_lab.unit,
            trend_delta=trend_delta,
            alert_kind=alert_kind,
            severity=(
                "critical"
                if (latest_lab.status or "").lower() == "critical"
                else "warning"
            ),
            reason=reason,
            source_type="lab_result",
            source_id=latest_lab.id,
            observed_at=latest_lab.collected_at,
            previous_observed_at=(
                previous_lab.collected_at if previous_lab is not None else None
            ),
            acknowledged=False,
        )
        db.add(alert)
        generated += 1

    if generated:
        await db.flush()

    total_unacked = await db.scalar(
        select(func.count())
        .select_from(PatientMetricAlert)
        .where(
            PatientMetricAlert.patient_id == patient_id,
            PatientMetricAlert.acknowledged.is_(False),
        )
    )

    return AlertsEvaluateResponse(
        generated=generated,
        total_active_unacknowledged=int(total_unacked or 0),
    )


@router.post(
    "/patient/{patient_id}/alerts/evaluate",
    response_model=AlertsEvaluateResponse,
)
async def evaluate_metric_alerts(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Evaluate watchlist metrics against latest labs and generate alerts."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    return await evaluate_metric_alerts_for_patient(patient_id=patient_id, db=db)


@router.post(
    "/patient/{patient_id}/alerts/{alert_id}/ack",
    response_model=MetricAlertResponse,
)
async def acknowledge_alert(
    patient_id: int,
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Acknowledge a metric alert."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    result = await db.execute(
        select(PatientMetricAlert).where(
            and_(
                PatientMetricAlert.id == alert_id,
                PatientMetricAlert.patient_id == patient_id,
            )
        )
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acknowledged = True
    alert.acknowledged_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(alert)
    return alert
