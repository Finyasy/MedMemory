"""Data ingestion API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_patient_for_user
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


async def _ensure_patient_ids_for_user(
    patient_ids: set[int],
    db: AsyncSession,
    current_user: User,
) -> None:
    if not patient_ids:
        return
    result = await db.execute(
        select(Patient.id).where(Patient.user_id == current_user.id, Patient.id.in_(patient_ids))
    )
    owned_ids = {row[0] for row in result.all()}
    missing = patient_ids - owned_ids
    if missing:
        raise HTTPException(status_code=404, detail="Patient not found")


# ============================================
# Lab Results Ingestion
# ============================================

@router.post("/labs", response_model=LabResultResponse, status_code=201)
async def ingest_lab_result(
    data: LabResultIngest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest a single lab result."""
    await get_patient_for_user(patient_id=data.patient_id, db=db, current_user=current_user)
    service = LabIngestionService(db, user_id=current_user.id)
    try:
        lab = await service.ingest_single(data.model_dump())
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
    await _ensure_patient_ids_for_user(
        {item.patient_id for item in data},
        db=db,
        current_user=current_user,
    )
    service = LabIngestionService(db, user_id=current_user.id)
    result = await service.ingest_batch([d.model_dump() for d in data])
    return IngestionResultResponse(**result.to_dict())


@router.post("/labs/panel", response_model=list[LabResultResponse], status_code=201)
async def ingest_lab_panel(
    data: LabPanelIngest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest a complete lab panel (multiple related tests)."""
    service = LabIngestionService(db, user_id=current_user.id)
    try:
        labs = await service.ingest_panel(
            patient_id=data.patient_id,
            panel_name=data.panel_name,
            results=[r.model_dump() for r in data.results],
            collected_at=data.collected_at,
            ordering_provider=data.ordering_provider,
        )
        return [LabResultResponse.model_validate(lab) for lab in labs]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Medication Ingestion
# ============================================

@router.post("/medications", response_model=MedicationResponse, status_code=201)
async def ingest_medication(
    data: MedicationIngest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest a single medication/prescription."""
    await get_patient_for_user(patient_id=data.patient_id, db=db, current_user=current_user)
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


@router.post("/medications/{medication_id}/discontinue", response_model=MedicationResponse)
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


# ============================================
# Encounter Ingestion
# ============================================

@router.post("/encounters", response_model=EncounterResponse, status_code=201)
async def ingest_encounter(
    data: EncounterIngest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest a single medical encounter/visit."""
    await get_patient_for_user(patient_id=data.patient_id, db=db, current_user=current_user)
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


# ============================================
# Batch Ingestion (Multiple Types)
# ============================================

@router.post("/batch", response_model=dict)
async def ingest_batch(
    data: BatchIngestionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ingest multiple record types in a single request.
    
    This endpoint allows you to ingest labs, medications, and encounters
    all at once, which is useful for importing data from EHR exports.
    """
    results = {}
    
    if data.labs:
        await _ensure_patient_ids_for_user(
            {item.patient_id for item in data.labs},
            db=db,
            current_user=current_user,
        )
        service = LabIngestionService(db, user_id=current_user.id)
        result = await service.ingest_batch([d.model_dump() for d in data.labs])
        results["labs"] = result.to_dict()
    
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
    
    # Calculate totals
    total_created = sum(r.get("records_created", 0) for r in results.values())
    total_errors = sum(len(r.get("errors", [])) for r in results.values())
    
    return {
        "success": total_errors == 0,
        "total_records_created": total_created,
        "total_errors": total_errors,
        "details": results,
    }
    await get_patient_for_user(patient_id=data.patient_id, db=db, current_user=current_user)
