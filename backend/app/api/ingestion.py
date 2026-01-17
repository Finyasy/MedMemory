"""Data ingestion API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
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


# ============================================
# Lab Results Ingestion
# ============================================

@router.post("/labs", response_model=LabResultResponse, status_code=201)
async def ingest_lab_result(
    data: LabResultIngest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a single lab result."""
    service = LabIngestionService(db)
    try:
        lab = await service.ingest_single(data.model_dump())
        return LabResultResponse.model_validate(lab)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/labs/batch", response_model=IngestionResultResponse)
async def ingest_lab_results_batch(
    data: list[LabResultIngest],
    db: AsyncSession = Depends(get_db),
):
    """Ingest multiple lab results in a batch."""
    service = LabIngestionService(db)
    result = await service.ingest_batch([d.model_dump() for d in data])
    return IngestionResultResponse(**result.to_dict())


@router.post("/labs/panel", response_model=list[LabResultResponse], status_code=201)
async def ingest_lab_panel(
    data: LabPanelIngest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a complete lab panel (multiple related tests)."""
    service = LabIngestionService(db)
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
):
    """Ingest a single medication/prescription."""
    service = MedicationIngestionService(db)
    try:
        med = await service.ingest_single(data.model_dump())
        return MedicationResponse.model_validate(med)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/medications/batch", response_model=IngestionResultResponse)
async def ingest_medications_batch(
    data: list[MedicationIngest],
    db: AsyncSession = Depends(get_db),
):
    """Ingest multiple medications in a batch."""
    service = MedicationIngestionService(db)
    result = await service.ingest_batch([d.model_dump() for d in data])
    return IngestionResultResponse(**result.to_dict())


@router.post("/medications/{medication_id}/discontinue", response_model=MedicationResponse)
async def discontinue_medication(
    medication_id: int,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Discontinue an active medication."""
    service = MedicationIngestionService(db)
    try:
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
):
    """Ingest a single medical encounter/visit."""
    service = EncounterIngestionService(db)
    try:
        encounter = await service.ingest_single(data.model_dump())
        return EncounterResponse.model_validate(encounter)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/encounters/batch", response_model=IngestionResultResponse)
async def ingest_encounters_batch(
    data: list[EncounterIngest],
    db: AsyncSession = Depends(get_db),
):
    """Ingest multiple encounters in a batch."""
    service = EncounterIngestionService(db)
    result = await service.ingest_batch([d.model_dump() for d in data])
    return IngestionResultResponse(**result.to_dict())


# ============================================
# Batch Ingestion (Multiple Types)
# ============================================

@router.post("/batch", response_model=dict)
async def ingest_batch(
    data: BatchIngestionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest multiple record types in a single request.
    
    This endpoint allows you to ingest labs, medications, and encounters
    all at once, which is useful for importing data from EHR exports.
    """
    results = {}
    
    if data.labs:
        service = LabIngestionService(db)
        result = await service.ingest_batch([d.model_dump() for d in data.labs])
        results["labs"] = result.to_dict()
    
    if data.medications:
        service = MedicationIngestionService(db)
        result = await service.ingest_batch([d.model_dump() for d in data.medications])
        results["medications"] = result.to_dict()
    
    if data.encounters:
        service = EncounterIngestionService(db)
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
