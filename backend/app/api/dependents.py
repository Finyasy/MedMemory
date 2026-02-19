"""Dependents management API endpoints."""

from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_authenticated_user
from app.database import get_db
from app.models import Document, Patient, PatientRelationship, User
from app.schemas.profile import (
    DependentCreate,
    DependentResponse,
    DependentUpdate,
    FamilyOverviewMember,
    FamilyOverviewResponse,
)

router = APIRouter(prefix="/dependents", tags=["Dependents"])
logger = logging.getLogger(__name__)


async def get_caretaker_patient(db: AsyncSession, user: User) -> Patient:
    """Get the primary (non-dependent) patient for the user."""
    result = await db.execute(
        select(Patient)
        .where(
            Patient.user_id == user.id,
            Patient.is_dependent.is_(False),
        )
        .order_by(Patient.created_at.asc(), Patient.id.asc())
        .limit(2)
    )
    patients = result.scalars().all()
    if not patients:
        raise HTTPException(status_code=404, detail="No primary patient profile found")
    if len(patients) > 1:
        logger.warning(
            "Multiple primary patient rows found for user_id=%s, selecting patient_id=%s",
            user.id,
            patients[0].id,
        )
    return patients[0]


@router.get("", response_model=list[DependentResponse])
async def list_dependents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List all dependents for the current user."""
    caretaker = await get_caretaker_patient(db, current_user)

    result = await db.execute(
        select(PatientRelationship)
        .options(selectinload(PatientRelationship.dependent))
        .where(PatientRelationship.caretaker_patient_id == caretaker.id)
    )
    relationships = result.scalars().all()

    dependents = []
    for rel in relationships:
        dep = rel.dependent
        dependents.append(
            DependentResponse(
                id=dep.id,
                first_name=dep.first_name,
                last_name=dep.last_name,
                full_name=dep.full_name,
                date_of_birth=dep.date_of_birth,
                age=dep.age,
                sex=dep.sex,
                blood_type=dep.blood_type,
                relationship_type=rel.relationship_type,
                is_primary_caretaker=rel.is_primary_caretaker,
                can_edit=rel.can_edit,
            )
        )

    return dependents


@router.post("", response_model=DependentResponse, status_code=201)
async def create_dependent(
    data: DependentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Add a new dependent."""
    caretaker = await get_caretaker_patient(db, current_user)

    # Create new patient for the dependent
    dependent = Patient(
        user_id=current_user.id,
        first_name=data.first_name,
        last_name=data.last_name,
        date_of_birth=data.date_of_birth,
        sex=data.sex,
        blood_type=data.blood_type,
        is_dependent=True,
    )
    db.add(dependent)
    await db.flush()

    # Create relationship
    relationship = PatientRelationship(
        caretaker_patient_id=caretaker.id,
        dependent_patient_id=dependent.id,
        relationship_type=data.relationship_type,
        is_primary_caretaker=True,
        can_edit=True,
        verified_at=datetime.utcnow(),
    )
    db.add(relationship)
    await db.flush()
    await db.refresh(dependent)

    return DependentResponse(
        id=dependent.id,
        first_name=dependent.first_name,
        last_name=dependent.last_name,
        full_name=dependent.full_name,
        date_of_birth=dependent.date_of_birth,
        age=dependent.age,
        sex=dependent.sex,
        blood_type=dependent.blood_type,
        relationship_type=data.relationship_type,
        is_primary_caretaker=True,
        can_edit=True,
    )


@router.get("/{dependent_id}", response_model=DependentResponse)
async def get_dependent(
    dependent_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get a specific dependent's details."""
    caretaker = await get_caretaker_patient(db, current_user)

    result = await db.execute(
        select(PatientRelationship)
        .options(selectinload(PatientRelationship.dependent))
        .where(
            PatientRelationship.caretaker_patient_id == caretaker.id,
            PatientRelationship.dependent_patient_id == dependent_id,
        )
    )
    rel = result.scalar_one_or_none()

    if not rel:
        raise HTTPException(status_code=404, detail="Dependent not found")

    dep = rel.dependent
    return DependentResponse(
        id=dep.id,
        first_name=dep.first_name,
        last_name=dep.last_name,
        full_name=dep.full_name,
        date_of_birth=dep.date_of_birth,
        age=dep.age,
        sex=dep.sex,
        blood_type=dep.blood_type,
        relationship_type=rel.relationship_type,
        is_primary_caretaker=rel.is_primary_caretaker,
        can_edit=rel.can_edit,
    )


@router.put("/{dependent_id}", response_model=DependentResponse)
async def update_dependent(
    dependent_id: int,
    data: DependentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update a dependent's information."""
    caretaker = await get_caretaker_patient(db, current_user)

    result = await db.execute(
        select(PatientRelationship)
        .options(selectinload(PatientRelationship.dependent))
        .where(
            PatientRelationship.caretaker_patient_id == caretaker.id,
            PatientRelationship.dependent_patient_id == dependent_id,
        )
    )
    rel = result.scalar_one_or_none()

    if not rel:
        raise HTTPException(status_code=404, detail="Dependent not found")

    if not rel.can_edit:
        raise HTTPException(
            status_code=403, detail="You don't have edit permissions for this dependent"
        )

    dep = rel.dependent
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dep, field, value)

    await db.flush()
    await db.refresh(dep)

    return DependentResponse(
        id=dep.id,
        first_name=dep.first_name,
        last_name=dep.last_name,
        full_name=dep.full_name,
        date_of_birth=dep.date_of_birth,
        age=dep.age,
        sex=dep.sex,
        blood_type=dep.blood_type,
        relationship_type=rel.relationship_type,
        is_primary_caretaker=rel.is_primary_caretaker,
        can_edit=rel.can_edit,
    )


@router.delete("/{dependent_id}", status_code=204)
async def remove_dependent(
    dependent_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Remove a dependent (unlinks relationship, doesn't delete data)."""
    caretaker = await get_caretaker_patient(db, current_user)

    result = await db.execute(
        select(PatientRelationship).where(
            PatientRelationship.caretaker_patient_id == caretaker.id,
            PatientRelationship.dependent_patient_id == dependent_id,
        )
    )
    rel = result.scalar_one_or_none()

    if not rel:
        raise HTTPException(status_code=404, detail="Dependent not found")

    # Note: db.delete() is synchronous in SQLAlchemy, commit handled by middleware
    db.delete(rel)


@router.get("/family/overview", response_model=FamilyOverviewResponse)
async def get_family_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get overview of all family members including self and dependents."""
    # Get the primary patient (self)
    result = await db.execute(
        select(Patient).where(
            Patient.user_id == current_user.id,
            Patient.is_dependent.is_(False),
        )
    )
    primary = result.scalar_one_or_none()

    members = []

    if primary:
        # Get document count for primary
        doc_count_result = await db.execute(
            select(func.count(Document.id)).where(Document.patient_id == primary.id)
        )
        doc_count = doc_count_result.scalar() or 0

        # Get last activity
        last_doc_result = await db.execute(
            select(Document.created_at)
            .where(Document.patient_id == primary.id)
            .order_by(Document.created_at.desc())
            .limit(1)
        )
        last_activity = last_doc_result.scalar_one_or_none()

        members.append(
            FamilyOverviewMember(
                id=primary.id,
                full_name=primary.full_name,
                age=primary.age,
                sex=primary.sex,
                blood_type=primary.blood_type,
                relationship_type=None,
                document_count=doc_count,
                last_activity=last_activity,
                alerts=[],
            )
        )

        # Get dependents
        rel_result = await db.execute(
            select(PatientRelationship)
            .options(selectinload(PatientRelationship.dependent))
            .where(PatientRelationship.caretaker_patient_id == primary.id)
        )
        relationships = rel_result.scalars().all()

        for rel in relationships:
            dep = rel.dependent

            # Get document count
            dep_doc_result = await db.execute(
                select(func.count(Document.id)).where(Document.patient_id == dep.id)
            )
            dep_doc_count = dep_doc_result.scalar() or 0

            # Get last activity
            dep_last_doc = await db.execute(
                select(Document.created_at)
                .where(Document.patient_id == dep.id)
                .order_by(Document.created_at.desc())
                .limit(1)
            )
            dep_last_activity = dep_last_doc.scalar_one_or_none()

            members.append(
                FamilyOverviewMember(
                    id=dep.id,
                    full_name=dep.full_name,
                    age=dep.age,
                    sex=dep.sex,
                    blood_type=dep.blood_type,
                    relationship_type=rel.relationship_type,
                    document_count=dep_doc_count,
                    last_activity=dep_last_activity,
                    alerts=[],
                )
            )

    return FamilyOverviewResponse(members=members)
