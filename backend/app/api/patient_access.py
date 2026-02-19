"""Patient access grant API: patient owner approves or revokes clinician access."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_db
from app.models import Patient, PatientAccessGrant, User
from app.schemas.clinician import (
    AccessGrantResponse,
    PatientAccessGrantApprove,
    PatientAccessRequestItem,
    PatientAccessRevoke,
)

router = APIRouter(prefix="/patient", tags=["Patient Access"])


@router.get("/access/requests", response_model=list[PatientAccessRequestItem])
async def list_patient_access_requests(
    status_filter: str | None = Query(
        None, description="Filter: pending, active, revoked, expired"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List access requests/grants for the current user's patients."""
    patients_result = await db.execute(
        select(Patient).where(Patient.user_id == current_user.id)
    )
    patients = {p.id: p for p in patients_result.scalars().all()}
    if not patients:
        return []
    patient_ids = list(patients.keys())
    stmt = (
        select(PatientAccessGrant, User)
        .join(User, User.id == PatientAccessGrant.clinician_user_id)
        .where(PatientAccessGrant.patient_id.in_(patient_ids))
    )
    if status_filter:
        stmt = stmt.where(PatientAccessGrant.status == status_filter)
    stmt = stmt.order_by(PatientAccessGrant.created_at.desc())
    result = await db.execute(stmt)
    rows = result.all()
    return [
        PatientAccessRequestItem(
            grant_id=g.id,
            patient_id=g.patient_id,
            patient_name=patients[g.patient_id].full_name,
            clinician_user_id=g.clinician_user_id,
            clinician_name=clinician.full_name or clinician.email,
            clinician_email=clinician.email,
            status=g.status,
            scopes=g.scopes,
            created_at=g.created_at,
        )
        for g, clinician in rows
    ]


@router.post("/access/grant", response_model=AccessGrantResponse)
async def approve_access_grant(
    data: PatientAccessGrantApprove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Patient owner approves a pending access request from a clinician."""
    result = await db.execute(
        select(PatientAccessGrant).where(PatientAccessGrant.id == data.grant_id)
    )
    grant = result.scalar_one_or_none()
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found"
        )
    patient_result = await db.execute(
        select(Patient).where(Patient.id == grant.patient_id)
    )
    patient = patient_result.scalar_one_or_none()
    if not patient or patient.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the patient owner can approve this grant",
        )
    if grant.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Grant is not pending (status: {grant.status})",
        )
    grant.status = "active"
    grant.granted_at = datetime.now(UTC)
    grant.granted_by_user_id = current_user.id
    if data.scopes:
        grant.scopes = data.scopes
    if data.expires_in_days:
        grant.expires_at = datetime.now(UTC) + timedelta(days=data.expires_in_days)
    await db.commit()
    await db.refresh(grant)
    return AccessGrantResponse.model_validate(grant)


@router.post("/access/revoke", response_model=AccessGrantResponse)
async def revoke_access_grant(
    data: PatientAccessRevoke,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Patient owner revokes a clinician's access."""
    result = await db.execute(
        select(PatientAccessGrant).where(PatientAccessGrant.id == data.grant_id)
    )
    grant = result.scalar_one_or_none()
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found"
        )
    patient_result = await db.execute(
        select(Patient).where(Patient.id == grant.patient_id)
    )
    patient = patient_result.scalar_one_or_none()
    if not patient or patient.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the patient owner can revoke this grant",
        )
    grant.status = "revoked"
    await db.commit()
    await db.refresh(grant)
    return AccessGrantResponse.model_validate(grant)
