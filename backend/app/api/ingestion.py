"""Data ingestion API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_patient_for_user
from app.config import settings
from app.database import get_db
from app.models import Medication, Patient, User
from app.schemas.ingestion import (
    BatchIngestionRequest,
    EncounterIngest,
    EncounterResponse,
    IngestionResultResponse,
    LabPanelIngest,
    LabResultIngest,
    LabResultResponse,
    MedicationIngest,
    MedicationResponse,
)
from app.services.ingestion import (
    EncounterIngestionService,
    LabIngestionService,
    MedicationIngestionService,
)

router = APIRouter(prefix="/ingest", tags=["Data Ingestion"])
logger = logging.getLogger(__name__)


async def _ensure_patient_ids_for_user(
    patient_ids: set[int],
    db: AsyncSession,
    current_user: User,
) -> None:
    if not patient_ids:
        return
    result = await db.execute(
        select(Patient.id).where(
            Patient.user_id == current_user.id, Patient.id.in_(patient_ids)
        )
    )
    owned_ids = {row[0] for row in result.all()}
    missing = patient_ids - owned_ids
    if missing:
        raise HTTPException(status_code=404, detail="Patient not found")


async def _auto_evaluate_alerts_after_lab_ingestion(
    *,
    patient_ids: set[int],
    db: AsyncSession,
) -> None:
    if not settings.dashboard_auto_evaluate_alerts_on_ingest:
        return
    if not patient_ids:
        return
    from app.api.dashboard import evaluate_metric_alerts_for_patient

    for patient_id in sorted(patient_ids):
        try:
            await evaluate_metric_alerts_for_patient(patient_id=patient_id, db=db)
        except Exception:
            logger.exception(
                "Automatic alert evaluation failed after lab ingestion for patient %s",
                patient_id,
            )


async def _auto_refresh_daily_summary_after_lab_ingestion(
    *,
    patient_ids: set[int],
    db: AsyncSession,
) -> None:
    if not settings.dashboard_auto_refresh_metric_summary_on_ingest:
        return
    if not patient_ids:
        return
    from app.api.dashboard import refresh_patient_metric_daily_summary

    for patient_id in sorted(patient_ids):
        try:
            await refresh_patient_metric_daily_summary(patient_id=patient_id, db=db)
        except Exception:
            logger.exception(
                "Automatic dashboard summary refresh failed after lab ingestion for patient %s",
                patient_id,
            )


async def _post_lab_ingestion_automation(
    *,
    patient_ids: set[int],
    db: AsyncSession,
) -> None:
    await _auto_refresh_daily_summary_after_lab_ingestion(
        patient_ids=patient_ids,
        db=db,
    )
    await _auto_evaluate_alerts_after_lab_ingestion(
        patient_ids=patient_ids,
        db=db,
    )


@router.post("/labs", response_model=LabResultResponse, status_code=201)
async def ingest_lab_result(
    data: LabResultIngest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest a single lab result."""
    await get_patient_for_user(
        patient_id=data.patient_id, db=db, current_user=current_user
    )
    service = LabIngestionService(db, user_id=current_user.id)
    try:
        lab = await service.ingest_single(data.model_dump())
        await _post_lab_ingestion_automation(
            patient_ids={lab.patient_id},
            db=db,
        )
        return LabResultResponse.model_validate(lab)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/labs/batch", response_model=IngestionResultResponse)
async def ingest_lab_results_batch(
    data: list[LabResultIngest],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest multiple lab results in a batch."""
    patient_ids = {item.patient_id for item in data if item.patient_id is not None}
    await _ensure_patient_ids_for_user(
        patient_ids,
        db=db,
        current_user=current_user,
    )
    service = LabIngestionService(db, user_id=current_user.id)
    result = await service.ingest_batch([d.model_dump() for d in data])
    created = int(getattr(result, "records_created", getattr(result, "created", 0)) or 0)
    if created > 0:
        await _post_lab_ingestion_automation(
            patient_ids=patient_ids,
            db=db,
        )
    return IngestionResultResponse(**result.to_dict())


@router.post("/labs/panel", response_model=list[LabResultResponse], status_code=201)
async def ingest_lab_panel(
    data: LabPanelIngest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest a complete lab panel (multiple related tests)."""
    await get_patient_for_user(
        patient_id=data.patient_id, db=db, current_user=current_user
    )
    service = LabIngestionService(db, user_id=current_user.id)
    try:
        labs = await service.ingest_panel(
            patient_id=data.patient_id,
            panel_name=data.panel_name,
            results=[r.model_dump() for r in data.results],
            collected_at=data.collected_at,
            ordering_provider=data.ordering_provider,
        )
        if labs:
            await _post_lab_ingestion_automation(
                patient_ids={data.patient_id},
                db=db,
            )
        return [LabResultResponse.model_validate(lab) for lab in labs]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/medications", response_model=MedicationResponse, status_code=201)
async def ingest_medication(
    data: MedicationIngest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest a single medication/prescription."""
    await get_patient_for_user(
        patient_id=data.patient_id, db=db, current_user=current_user
    )
    service = MedicationIngestionService(db, user_id=current_user.id)
    try:
        med = await service.ingest_single(data.model_dump())
        return MedicationResponse.model_validate(med)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/medications/batch", response_model=IngestionResultResponse)
async def ingest_medications_batch(
    data: list[MedicationIngest],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest multiple medications in a batch."""
    await _ensure_patient_ids_for_user(
        {item.patient_id for item in data},
        db=db,
        current_user=current_user,
    )
    service = MedicationIngestionService(db, user_id=current_user.id)
    result = await service.ingest_batch([d.model_dump() for d in data])
    return IngestionResultResponse(**result.to_dict())


@router.post(
    "/medications/{medication_id}/discontinue", response_model=MedicationResponse
)
async def discontinue_medication(
    medication_id: int,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Discontinue an active medication."""
    try:
        result = await db.execute(
            select(Medication).where(Medication.id == medication_id)
        )
        medication = result.scalar_one_or_none()
        if not medication:
            raise HTTPException(status_code=404, detail="Medication not found")
        await get_patient_for_user(
            patient_id=medication.patient_id,
            db=db,
            current_user=current_user,
        )

        service = MedicationIngestionService(db, user_id=current_user.id)
        med = await service.discontinue_medication(medication_id, reason=reason)
        return MedicationResponse.model_validate(med)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/encounters", response_model=EncounterResponse, status_code=201)
async def ingest_encounter(
    data: EncounterIngest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest a single medical encounter/visit."""
    await get_patient_for_user(
        patient_id=data.patient_id, db=db, current_user=current_user
    )
    service = EncounterIngestionService(db, user_id=current_user.id)
    try:
        encounter = await service.ingest_single(data.model_dump())
        return EncounterResponse.model_validate(encounter)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/encounters/batch", response_model=IngestionResultResponse)
async def ingest_encounters_batch(
    data: list[EncounterIngest],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest multiple encounters in a batch."""
    await _ensure_patient_ids_for_user(
        {item.patient_id for item in data},
        db=db,
        current_user=current_user,
    )
    service = EncounterIngestionService(db, user_id=current_user.id)
    result = await service.ingest_batch([d.model_dump() for d in data])
    return IngestionResultResponse(**result.to_dict())


@router.post("/batch", response_model=dict)
async def ingest_batch(
    data: BatchIngestionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest multiple record types in a single request."""
    results = {}
    lab_patient_ids_ingested: set[int] = set()

    if data.labs:
        lab_patient_ids = {item.patient_id for item in data.labs if item.patient_id is not None}
        await _ensure_patient_ids_for_user(
            lab_patient_ids,
            db=db,
            current_user=current_user,
        )
        service = LabIngestionService(db, user_id=current_user.id)
        result = await service.ingest_batch([d.model_dump() for d in data.labs])
        labs_result = result.to_dict()
        results["labs"] = labs_result
        if int(labs_result.get("records_created", 0) or 0) > 0:
            lab_patient_ids_ingested.update(lab_patient_ids)

    if data.medications:
        await _ensure_patient_ids_for_user(
            {item.patient_id for item in data.medications},
            db=db,
            current_user=current_user,
        )
        service = MedicationIngestionService(db, user_id=current_user.id)
        result = await service.ingest_batch([d.model_dump() for d in data.medications])
        results["medications"] = result.to_dict()

    if data.encounters:
        await _ensure_patient_ids_for_user(
            {item.patient_id for item in data.encounters},
            db=db,
            current_user=current_user,
        )
        service = EncounterIngestionService(db, user_id=current_user.id)
        result = await service.ingest_batch([d.model_dump() for d in data.encounters])
        results["encounters"] = result.to_dict()
    total_created = sum(r.get("records_created", 0) for r in results.values())
    total_errors = sum(len(r.get("errors", [])) for r in results.values())
    if lab_patient_ids_ingested:
        await _post_lab_ingestion_automation(
            patient_ids=lab_patient_ids_ingested,
            db=db,
        )

    return {
        "success": total_errors == 0,
        "total_records_created": total_created,
        "total_errors": total_errors,
        "details": results,
    }
