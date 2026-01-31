"""Shared API dependencies."""

from datetime import datetime, timezone
from typing import Annotated

import asyncio
import time

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Patient, PatientAccessGrant, User

security = HTTPBearer()

_auth_rate_limit: dict[str, tuple[int, float]] = {}
_auth_rate_limit_lock = asyncio.Lock()


async def require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")):
    """Require API key when configured (fallback for backward compatibility)."""
    if not settings.api_key:
        return None
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return None


async def get_authenticated_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    """Get authenticated user from valid JWT access token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        
        user_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        jti: str | None = payload.get("jti")
        
        if user_id_str is None:
            raise credentials_exception
        if token_type and token_type != "access":
            raise credentials_exception
        if jti:
            from app.api.auth import is_token_blacklisted
            if await is_token_blacklisted(jti):
                raise credentials_exception
        
        user_id = int(user_id_str)
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return user


async def get_patient_for_user(
    patient_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
) -> Patient:
    """Fetch a patient owned by the current user or raise."""
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.user_id == current_user.id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


async def get_authorized_patient(
    patient_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
    scope: str | None = None,
) -> Patient:
    """Fetch a patient the current user is allowed to access: owner or clinician with active grant.
    Optionally require a scope (documents, records, labs, medications, chat)."""
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if patient.user_id == current_user.id:
        return patient
    grant_result = await db.execute(
        select(PatientAccessGrant).where(
            PatientAccessGrant.patient_id == patient_id,
            PatientAccessGrant.clinician_user_id == current_user.id,
            PatientAccessGrant.status == "active",
            or_(
                PatientAccessGrant.expires_at.is_(None),
                PatientAccessGrant.expires_at > datetime.now(timezone.utc),
            ),
        )
    )
    grant = grant_result.scalar_one_or_none()
    if not grant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access not granted to this patient")
    if scope and not grant.has_scope(scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Grant does not include scope: {scope}")
    return patient


async def require_clinician(
    current_user: Annotated[User, Depends(get_authenticated_user)],
) -> User:
    """Require the current user to have role clinician. Use for clinician-only endpoints."""
    if getattr(current_user, "role", "patient") != "clinician":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clinician access required",
        )
    return current_user


async def rate_limit_auth(request: Request) -> None:
    """Basic in-memory rate limiter for auth endpoints."""
    window = settings.auth_rate_limit_window_seconds
    max_requests = settings.auth_rate_limit_max_requests
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()

    async with _auth_rate_limit_lock:
        count, reset_at = _auth_rate_limit.get(client_ip, (0, now + window))
        if now > reset_at:
            count = 0
            reset_at = now + window
        count += 1
        _auth_rate_limit[client_ip] = (count, reset_at)

        if count > max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )
