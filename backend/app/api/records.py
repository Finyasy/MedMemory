from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.records import RecordCreate, RecordResponse
from app.services.records import RecordRepository, SQLRecordRepository

router = APIRouter(prefix="/records", tags=["Medical Records"])


def get_record_repo(
    db: AsyncSession = Depends(get_db),
) -> RecordRepository:
    return SQLRecordRepository(db)


@router.get("/", response_model=list[RecordResponse])
async def list_records(
    patient_id: Optional[int] = Query(None, description="Filter by patient ID"),
    record_type: Optional[str] = Query(None, description="Filter by record type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    repo: RecordRepository = Depends(get_record_repo),
):
    """List all medical records with optional filtering."""
    records = await repo.list_records(
        patient_id=patient_id,
        record_type=record_type,
        skip=skip,
        limit=limit,
    )
    
    return [RecordResponse.model_validate(r) for r in records]


@router.post("/", response_model=RecordResponse, status_code=201)
async def create_record(
    record: RecordCreate,
    patient_id: int = Query(..., description="Patient ID for this record"),
    repo: RecordRepository = Depends(get_record_repo),
):
    """Create a new medical record."""
    try:
        new_record = await repo.create_record(patient_id=patient_id, record=record)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    
    return RecordResponse.model_validate(new_record)


@router.get("/{record_id}", response_model=RecordResponse)
async def get_record(
    record_id: int,
    repo: RecordRepository = Depends(get_record_repo),
):
    """Get a specific medical record by ID."""
    record = await repo.get_record(record_id)
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    return RecordResponse.model_validate(record)


@router.delete("/{record_id}", status_code=204)
async def delete_record(
    record_id: int,
    repo: RecordRepository = Depends(get_record_repo),
):
    """Delete a medical record."""
    deleted = await repo.delete_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
