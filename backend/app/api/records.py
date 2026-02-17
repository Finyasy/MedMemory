from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_patient_for_user
from app.database import get_db
from app.config import settings
from app.models import User
from app.schemas.records import RecordCreate, RecordResponse
from app.services.records import RecordRepository, SQLRecordRepository
from app.utils.cache import CacheKeys, clear_cache, get_cached, set_cached

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List all medical records with optional filtering."""
    if patient_id is not None:
        await get_patient_for_user(patient_id=patient_id, db=db, current_user=current_user)
    cache_key = CacheKeys.records(current_user.id, patient_id, record_type, skip, limit)
    cached = await get_cached(cache_key)
    if cached is not None:
        return cached
    records = await repo.list_records(
        patient_id=patient_id,
        owner_user_id=current_user.id,
        record_type=record_type,
        skip=skip,
        limit=limit,
    )
    
    response = [RecordResponse.model_validate(r) for r in records]
    await set_cached(cache_key, response, ttl_seconds=settings.response_cache_ttl_seconds)
    return response


@router.post("/", response_model=RecordResponse, status_code=201)
async def create_record(
    record: RecordCreate,
    patient_id: int = Query(..., description="Patient ID for this record"),
    repo: RecordRepository = Depends(get_record_repo),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Create a new medical record."""
    await get_patient_for_user(patient_id=patient_id, db=db, current_user=current_user)
    try:
        new_record = await repo.create_record(patient_id=patient_id, record=record)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await clear_cache(f"records:{current_user.id}:")
    
    return RecordResponse.model_validate(new_record)


@router.get("/{record_id}", response_model=RecordResponse)
async def get_record(
    record_id: int,
    repo: RecordRepository = Depends(get_record_repo),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get a specific medical record by ID."""
    record = await repo.get_record(record_id)
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    await get_patient_for_user(patient_id=record.patient_id, db=db, current_user=current_user)
    
    return RecordResponse.model_validate(record)


@router.delete("/{record_id}", status_code=204)
async def delete_record(
    record_id: int,
    repo: RecordRepository = Depends(get_record_repo),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete a medical record."""
    record = await repo.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    await get_patient_for_user(patient_id=record.patient_id, db=db, current_user=current_user)
    deleted = await repo.delete_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    await clear_cache(f"records:{current_user.id}:")
