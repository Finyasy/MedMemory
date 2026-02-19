"""Clinician dashboard API: auth, profile, access grants, upload review."""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.api.auth import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.api.deps import (
    get_authenticated_user,
    get_authorized_patient,
    rate_limit_auth,
    require_clinician,
)
from app.config import settings
from app.database import get_db
from app.models import (
    ClinicianProfile,
    Document,
    Patient,
    PatientAccessGrant,
    User,
)
from app.schemas.auth import TokenResponse
from app.schemas.clinician import (
    AccessGrantResponse,
    AccessRequestCreate,
    ClinicianLogin,
    ClinicianProfileResponse,
    ClinicianProfileUpdate,
    ClinicianSignUp,
    PatientWithGrant,
)
from app.schemas.document import DocumentResponse
from app.schemas.records import RecordResponse
from app.services.records import SQLRecordRepository

logger = logging.getLogger("medmemory")

router = APIRouter(prefix="/clinician", tags=["Clinician"])


def _tokens_for_user(user: User) -> TokenResponse:
    role = getattr(user, "role", "patient")
    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": role},
        expires_delta=access_token_expires,
    )
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user_id=user.id,
        email=user.email,
    )


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_auth)],
)
async def clinician_signup(
    data: ClinicianSignUp,
    db: AsyncSession = Depends(get_db),
):
    """Create a clinician account (user with role=clinician + optional profile)."""
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    hashed = get_password_hash(data.password)
    user = User(
        email=data.email,
        hashed_password=hashed,
        full_name=data.full_name,
        is_active=True,
        role="clinician",
    )
    db.add(user)
    try:
        await db.flush()
    except (OperationalError, IntegrityError) as e:
        await db.rollback()
        logger.exception("Clinician signup DB error (migration may be missing): %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Database schema may be out of date. "
                "Run: cd backend && alembic upgrade head"
            ),
        ) from e
    profile = ClinicianProfile(
        user_id=user.id,
        license_number=data.registration_number,
        specialty=data.specialty,
        organization_name=data.organization_name,
        phone=data.phone,
        address=data.address,
    )
    db.add(profile)
    try:
        await db.commit()
        await db.refresh(user)
    except (OperationalError, IntegrityError) as e:
        await db.rollback()
        logger.exception("Clinician signup DB error (migration may be missing): %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Database schema may be out of date. "
                "Run: cd backend && alembic upgrade head"
            ),
        ) from e
    return _tokens_for_user(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit_auth)],
)
async def clinician_login(
    credentials: ClinicianLogin,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate clinician; returns tokens only if user has role=clinician."""
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    if getattr(user, "role", "patient") != "clinician":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a clinician account. Use the regular login for patient accounts.",
        )
    return _tokens_for_user(user)


@router.get("/profile", response_model=ClinicianProfileResponse)
async def get_clinician_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinician),
):
    """Get the current clinician's profile."""
    result = await db.execute(
        select(ClinicianProfile).where(ClinicianProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return ClinicianProfileResponse(
            user_id=current_user.id,
            email=current_user.email,
            full_name=current_user.full_name,
            npi=None,
            license_number=None,
            specialty=None,
            organization_name=None,
            phone=None,
            address=None,
            verified_at=None,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
        )
    return ClinicianProfileResponse(
        user_id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        npi=profile.npi,
        license_number=profile.license_number,
        specialty=profile.specialty,
        organization_name=profile.organization_name,
        phone=profile.phone,
        address=profile.address,
        verified_at=profile.verified_at,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.patch("/profile", response_model=ClinicianProfileResponse)
async def update_clinician_profile(
    data: ClinicianProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinician),
):
    """Update the current clinician's profile."""
    result = await db.execute(
        select(ClinicianProfile).where(ClinicianProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = ClinicianProfile(user_id=current_user.id)
        db.add(profile)
        await db.flush()
    update = data.model_dump(exclude_unset=True)
    if "full_name" in update:
        current_user.full_name = update["full_name"]
    for key in (
        "npi",
        "license_number",
        "specialty",
        "organization_name",
        "phone",
        "address",
    ):
        if key in update:
            setattr(profile, key, update[key])
    await db.commit()
    await db.refresh(profile)
    await db.refresh(current_user)
    return ClinicianProfileResponse(
        user_id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        npi=profile.npi,
        license_number=profile.license_number,
        specialty=profile.specialty,
        organization_name=profile.organization_name,
        phone=profile.phone,
        address=profile.address,
        verified_at=profile.verified_at,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.post(
    "/access/request",
    response_model=AccessGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_patient_access(
    data: AccessRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinician),
):
    """Request access to a patient (creates grant with status=pending). Patient owner must approve."""
    result = await db.execute(select(Patient).where(Patient.id == data.patient_id))
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )
    existing = await db.execute(
        select(PatientAccessGrant).where(
            PatientAccessGrant.patient_id == data.patient_id,
            PatientAccessGrant.clinician_user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access request already exists for this patient",
        )
    scopes = data.scopes or "documents,records,labs,medications,chat"
    expires_at = None
    if data.expires_in_days:
        expires_at = datetime.now(UTC) + timedelta(days=data.expires_in_days)
    grant = PatientAccessGrant(
        patient_id=data.patient_id,
        clinician_user_id=current_user.id,
        status="pending",
        scopes=scopes,
        expires_at=expires_at,
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return AccessGrantResponse.model_validate(grant)


@router.get("/patients", response_model=list[PatientWithGrant])
async def list_clinician_patients(
    status_filter: str | None = Query(
        None, description="Filter by grant status: active, pending, revoked, expired"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinician),
):
    """List patients the clinician has access to (or has requested access)."""
    query = (
        select(Patient, PatientAccessGrant)
        .join(PatientAccessGrant, PatientAccessGrant.patient_id == Patient.id)
        .where(PatientAccessGrant.clinician_user_id == current_user.id)
    )
    if status_filter:
        query = query.where(PatientAccessGrant.status == status_filter)
    query = query.order_by(PatientAccessGrant.created_at.desc())
    result = await db.execute(query)
    rows = result.all()
    return [
        PatientWithGrant(
            patient_id=p.id,
            patient_first_name=p.first_name,
            patient_last_name=p.last_name,
            patient_full_name=p.full_name,
            grant_id=g.id,
            grant_status=g.status,
            grant_scopes=g.scopes,
            granted_at=g.granted_at,
            expires_at=g.expires_at,
        )
        for p, g in rows
    ]


@router.get("/uploads", response_model=list[DocumentResponse])
async def list_clinician_uploads(
    patient_id: int | None = Query(None, description="Filter by patient ID"),
    status_filter: str | None = Query(None, description="Filter by processing_status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinician),
):
    """List documents across all patients the clinician has access to (with documents scope)."""
    now = datetime.now(UTC)
    grant_result = await db.execute(
        select(PatientAccessGrant).where(
            PatientAccessGrant.clinician_user_id == current_user.id,
            PatientAccessGrant.status == "active",
            or_(
                PatientAccessGrant.expires_at.is_(None),
                PatientAccessGrant.expires_at > now,
            ),
        )
    )
    grants = grant_result.scalars().all()
    scope_ok = [g.patient_id for g in grants if g.has_scope("documents")]
    if not scope_ok:
        return []
    query = (
        select(Document)
        .options(
            load_only(
                Document.id,
                Document.patient_id,
                Document.filename,
                Document.original_filename,
                Document.file_size,
                Document.mime_type,
                Document.document_type,
                Document.category,
                Document.title,
                Document.description,
                Document.document_date,
                Document.received_date,
                Document.processing_status,
                Document.is_processed,
                Document.processed_at,
                Document.page_count,
                Document.created_at,
            )
        )
        .where(Document.patient_id.in_(scope_ok))
    )
    if patient_id is not None:
        if patient_id not in scope_ok:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access not granted to this patient",
            )
        query = query.where(Document.patient_id == patient_id)
    if status_filter:
        query = query.where(Document.processing_status == status_filter)
    query = query.order_by(Document.received_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    documents = result.scalars().all()
    return [DocumentResponse.model_validate(d) for d in documents]


@router.get("/patient/{patient_id}/documents", response_model=list[DocumentResponse])
async def list_clinician_patient_documents(
    patient_id: int,
    document_type: str | None = Query(None),
    processed_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List documents for a patient the clinician has access to (documents scope)."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="documents",
    )
    query = (
        select(Document)
        .options(
            load_only(
                Document.id,
                Document.patient_id,
                Document.filename,
                Document.original_filename,
                Document.file_size,
                Document.mime_type,
                Document.document_type,
                Document.category,
                Document.title,
                Document.description,
                Document.document_date,
                Document.received_date,
                Document.processing_status,
                Document.is_processed,
                Document.processed_at,
                Document.page_count,
                Document.created_at,
            )
        )
        .where(Document.patient_id == patient_id)
    )
    if document_type:
        query = query.where(Document.document_type == document_type)
    if processed_only:
        query = query.where(Document.is_processed)
    query = query.order_by(Document.received_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    documents = result.scalars().all()
    return [DocumentResponse.model_validate(d) for d in documents]


@router.get("/patient/{patient_id}/records", response_model=list[RecordResponse])
async def list_clinician_patient_records(
    patient_id: int,
    record_type: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List medical records for a patient the clinician has access to (records scope)."""
    await get_authorized_patient(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
        scope="records",
    )
    repo = SQLRecordRepository(db)
    records_list = await repo.list_records(
        patient_id=patient_id,
        owner_user_id=None,
        record_type=record_type,
        skip=skip,
        limit=limit,
    )
    return [RecordResponse.model_validate(r) for r in records_list]
