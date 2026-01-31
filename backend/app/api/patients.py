from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import load_only
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_patient_for_user
from app.database import get_db
from app.config import settings
from app.utils.cache import CacheKeys, clear_cache, get_cached, set_cached
from app.models import Patient, User
from app.schemas.patient import (
    PatientCreate,
    PatientResponse,
    PatientSummary,
    PatientUpdate,
)

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("/", response_model=list[PatientSummary])
async def list_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List all patients with optional search."""
    cache_key = CacheKeys.patients(current_user.id, search, skip, limit)
    cached = await get_cached(cache_key)
    if cached is not None:
        return cached
    query = (
        select(Patient)
        .options(
            load_only(
                Patient.id,
                Patient.first_name,
                Patient.last_name,
                Patient.date_of_birth,
                Patient.gender,
            )
        )
        .where(Patient.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    
    if search:
        search_filter = f"%{search.lower()}%"
        query = query.where(
            (Patient.first_name.ilike(search_filter)) |
            (Patient.last_name.ilike(search_filter)) |
            (Patient.external_id.ilike(search_filter))
        )
    
    query = query.order_by(Patient.last_name, Patient.first_name)
    result = await db.execute(query)
    patients = result.scalars().all()
    
    response = [
        PatientSummary(
            id=p.id,
            full_name=p.full_name,
            date_of_birth=p.date_of_birth,
            age=p.age,
            gender=p.gender,
        )
        for p in patients
    ]
    await set_cached(cache_key, response, ttl_seconds=settings.response_cache_ttl_seconds)
    return response


@router.post("/", response_model=PatientResponse, status_code=201)
async def create_patient(
    patient_data: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Create a new patient."""
    # Check for duplicate external_id
    if patient_data.external_id:
        existing = await db.execute(
            select(Patient).where(Patient.external_id == patient_data.external_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Patient with external_id '{patient_data.external_id}' already exists"
            )
    
    patient = Patient(**patient_data.model_dump(), user_id=current_user.id)
    db.add(patient)
    await db.flush()
    await db.refresh(patient)
    await clear_cache(CacheKeys.patients_prefix(current_user.id))
    
    return PatientResponse.model_validate(patient, from_attributes=True)


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient: Patient = Depends(get_patient_for_user),
):
    """Get a specific patient by ID."""
    return PatientResponse.model_validate(patient, from_attributes=True)


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_data: PatientUpdate,
    patient: Patient = Depends(get_patient_for_user),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update a patient's information."""
    # Update only provided fields
    update_data = patient_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(patient, field, value)
    
    await db.flush()
    await db.refresh(patient)
    await clear_cache(CacheKeys.patients_prefix(current_user.id))
    
    return PatientResponse.model_validate(patient, from_attributes=True)


@router.delete("/{patient_id}", status_code=204)
async def delete_patient(
    patient: Patient = Depends(get_patient_for_user),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete a patient and all associated records."""
    # Delete patient (cascade deletes related records)
    # Note: db.delete() is synchronous in SQLAlchemy, commit handled by middleware
    db.delete(patient)
    await clear_cache(CacheKeys.patients_prefix(current_user.id))
