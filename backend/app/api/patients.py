from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Patient
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
):
    """List all patients with optional search."""
    query = select(Patient).offset(skip).limit(limit)
    
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
    
    return [
        PatientSummary(
            id=p.id,
            full_name=p.full_name,
            date_of_birth=p.date_of_birth,
            age=p.age,
            gender=p.gender,
        )
        for p in patients
    ]


@router.post("/", response_model=PatientResponse, status_code=201)
async def create_patient(
    patient_data: PatientCreate,
    db: AsyncSession = Depends(get_db),
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
    
    patient = Patient(**patient_data.model_dump())
    db.add(patient)
    await db.flush()
    await db.refresh(patient)
    
    return PatientResponse(
        id=patient.id,
        external_id=patient.external_id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        email=patient.email,
        phone=patient.phone,
        address=patient.address,
        blood_type=patient.blood_type,
        allergies=patient.allergies,
        medical_conditions=patient.medical_conditions,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
        full_name=patient.full_name,
        age=patient.age,
    )


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific patient by ID."""
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id)
    )
    patient = result.scalar_one_or_none()
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    return PatientResponse(
        id=patient.id,
        external_id=patient.external_id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        email=patient.email,
        phone=patient.phone,
        address=patient.address,
        blood_type=patient.blood_type,
        allergies=patient.allergies,
        medical_conditions=patient.medical_conditions,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
        full_name=patient.full_name,
        age=patient.age,
    )


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: int,
    patient_data: PatientUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a patient's information."""
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id)
    )
    patient = result.scalar_one_or_none()
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Update only provided fields
    update_data = patient_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(patient, field, value)
    
    await db.flush()
    await db.refresh(patient)
    
    return PatientResponse(
        id=patient.id,
        external_id=patient.external_id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        email=patient.email,
        phone=patient.phone,
        address=patient.address,
        blood_type=patient.blood_type,
        allergies=patient.allergies,
        medical_conditions=patient.medical_conditions,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
        full_name=patient.full_name,
        age=patient.age,
    )


@router.delete("/{patient_id}", status_code=204)
async def delete_patient(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a patient and all associated records."""
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id)
    )
    patient = result.scalar_one_or_none()
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    await db.delete(patient)
