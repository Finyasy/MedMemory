import asyncio
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_patient_for_user, rate_limit_auth
from app.config import settings
from app.database import get_db
from app.models import Patient, TokenBlacklist
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    MobileTokenRequest,
    MobileTokenResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLogin,
    UserResponse,
    UserSignUp,
)
from app.services.email import send_email

router = APIRouter(tags=["Authentication"])

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer()

_token_blacklist: set[str] = set()
_blacklist_lock = asyncio.Lock()


def _normalized_role(value: object, default: str = "patient") -> str:
    """Normalize role strings to avoid case/whitespace mismatches."""
    if value is None:
        return default
    role = str(value).strip().lower()
    return role or default


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using PBKDF2-SHA256."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
    jti = secrets.token_urlsafe(16)
    to_encode.update({"exp": expire, "type": "access", "jti": jti})
    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    jti = secrets.token_urlsafe(16)
    to_encode.update({"exp": expire, "type": "refresh", "jti": jti})
    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def _coerce_exp_datetime(exp: int | float | datetime | None) -> datetime | None:
    if exp is None:
        return None
    if isinstance(exp, datetime):
        return exp.astimezone(UTC) if exp.tzinfo else exp.replace(tzinfo=UTC)
    if isinstance(exp, (int, float)):
        return datetime.fromtimestamp(exp, tz=UTC)
    return None


async def is_token_blacklisted(
    jti: str,
    db: AsyncSession | None = None,
) -> bool:
    """Check if a token is blacklisted."""
    async with _blacklist_lock:
        in_memory = jti in _token_blacklist
    if in_memory:
        return True
    if db is None:
        return False
    result = await db.execute(
        select(TokenBlacklist.id).where(TokenBlacklist.jti == jti)
    )
    blacklisted = result.scalar_one_or_none()
    if blacklisted is None:
        return False
    return isinstance(blacklisted, int) or hasattr(blacklisted, "jti")


async def blacklist_token(
    jti: str,
    *,
    db: AsyncSession | None = None,
    token_type: str = "access",
    expires_at: datetime | None = None,
) -> None:
    """Add a token to the blacklist."""
    async with _blacklist_lock:
        _token_blacklist.add(jti)
    if db is None:
        return
    result = await db.execute(select(TokenBlacklist).where(TokenBlacklist.jti == jti))
    existing = result.scalar_one_or_none()
    if existing is not None and hasattr(existing, "jti"):
        return
    db.add(
        TokenBlacklist(
            jti=jti,
            token_type=token_type,
            expires_at=expires_at
            or (
                datetime.now(UTC)
                + timedelta(days=settings.jwt_refresh_token_expire_days)
            ),
        )
    )


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_mobile_scopes(scopes: list[str]) -> list[str]:
    allowed = {"chat", "records", "documents", "apple_health"}
    normalized = sorted(
        {
            scope.strip()
            for scope in scopes
            if isinstance(scope, str) and scope.strip() in allowed
        }
    )
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one valid mobile scope is required",
        )
    return normalized


def _issue_mobile_tokens(
    *,
    user: User,
    patient_id: int,
    scopes: list[str],
) -> tuple[str, str, int]:
    role = _normalized_role(getattr(user, "role", "patient"))
    token_claims = {
        "sub": str(user.id),
        "role": role,
        "mobile_patient_id": patient_id,
        "mobile_scopes": scopes,
        "aud": "mobile",
    }
    expires_in_seconds = settings.jwt_mobile_access_token_expire_minutes * 60
    access_token = create_access_token(
        data=token_claims,
        expires_delta=timedelta(minutes=settings.jwt_mobile_access_token_expire_minutes),
    )
    refresh_token = create_refresh_token(data=token_claims)
    return access_token, refresh_token, expires_in_seconds


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get the current authenticated user from JWT token.

    DEPRECATED: Use get_authenticated_user from app.api.deps instead.
    This function is kept for backward compatibility.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        user_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        jti: str | None = payload.get("jti")
        if user_id_str is None:
            raise credentials_exception
        if token_type != "access":
            raise credentials_exception
        if jti and await is_token_blacklisted(jti, db=db):
            raise credentials_exception
        user_id = int(user_id_str)
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
        )
    return user


@router.post(
    "/auth/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_auth)],
)
async def signup(user_data: UserSignUp, db: Annotated[AsyncSession, Depends(get_db)]):
    """Create a new user account."""
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    role = _normalized_role(getattr(new_user, "role", "patient"))
    access_token = create_access_token(
        data={"sub": str(new_user.id), "role": role}, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": str(new_user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user_id=new_user.id,
        email=new_user.email,
    )


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit_auth)],
)
async def login(credentials: UserLogin, db: Annotated[AsyncSession, Depends(get_db)]):
    """Authenticate user and return access and refresh tokens."""
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
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
        )

    role = _normalized_role(getattr(user, "role", "patient"))
    if role == "clinician":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Use the Clinician portal to sign in. Go to /clinician",
        )

    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": role}, expires_delta=access_token_expires
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


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_access_token(
    payload: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get new access token using refresh token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token_payload = jwt.decode(
            payload.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id_str: str | None = token_payload.get("sub")
        token_type: str | None = token_payload.get("type")
        jti: str | None = token_payload.get("jti")

        if user_id_str is None or token_type != "refresh":
            raise credentials_exception
        if jti and await is_token_blacklisted(jti, db=db):
            raise credentials_exception

        user_id = int(user_id_str)
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exception

    if jti:
        await blacklist_token(
            jti,
            db=db,
            token_type="refresh",
            expires_at=_coerce_exp_datetime(token_payload.get("exp")),
        )

    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    role = _normalized_role(getattr(user, "role", "patient"))
    access_token = create_access_token(
        data={"sub": str(user.id), "role": role}, expires_delta=access_token_expires
    )
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user_id=user.id,
        email=user.email,
    )


@router.post("/auth/mobile-token", response_model=MobileTokenResponse)
async def issue_mobile_token(
    payload: MobileTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    """Issue a short-lived patient-scoped token for the native mobile app."""
    patient = await get_patient_for_user(
        patient_id=payload.patient_id,
        db=db,
        current_user=current_user,
    )
    scopes = _normalize_mobile_scopes(payload.scopes)
    access_token, refresh_token, expires_in_seconds = _issue_mobile_tokens(
        user=current_user,
        patient_id=patient.id,
        scopes=scopes,
    )
    return MobileTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in_seconds,
        patient_id=patient.id,
        scopes=scopes,
    )


@router.post("/auth/mobile-refresh", response_model=MobileTokenResponse)
async def refresh_mobile_token(
    payload: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Refresh a patient-scoped mobile token using a mobile refresh token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid mobile refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token_payload = jwt.decode(
            payload.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id_str: str | None = token_payload.get("sub")
        token_type: str | None = token_payload.get("type")
        jti: str | None = token_payload.get("jti")
        audience: str | None = token_payload.get("aud")
        mobile_patient_id = token_payload.get("mobile_patient_id")
        raw_scopes = token_payload.get("mobile_scopes")

        if user_id_str is None or token_type != "refresh" or audience != "mobile":
            raise credentials_exception
        if mobile_patient_id is None:
            raise credentials_exception
        if jti and await is_token_blacklisted(jti, db=db):
            raise credentials_exception

        user_id = int(user_id_str)
        patient_id = int(mobile_patient_id)
        if isinstance(raw_scopes, list):
            scopes = _normalize_mobile_scopes([str(scope) for scope in raw_scopes])
        elif isinstance(raw_scopes, str):
            scopes = _normalize_mobile_scopes(raw_scopes.split(","))
        else:
            raise credentials_exception
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exception

    patient_result = await db.execute(
        select(Patient.id).where(Patient.id == patient_id, Patient.user_id == user.id)
    )
    if patient_result.scalar_one_or_none() is None:
        raise credentials_exception

    if jti:
        await blacklist_token(
            jti,
            db=db,
            token_type="refresh",
            expires_at=_coerce_exp_datetime(token_payload.get("exp")),
        )

    access_token, refresh_token, expires_in_seconds = _issue_mobile_tokens(
        user=user,
        patient_id=patient_id,
        scopes=scopes,
    )
    return MobileTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in_seconds,
        patient_id=patient_id,
        scopes=scopes,
    )


@router.post("/auth/logout")
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Logout and invalidate tokens."""
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        jti: str | None = payload.get("jti")
        token_type: str = payload.get("type", "access")
        if jti:
            await blacklist_token(
                jti,
                db=db,
                token_type=token_type,
                expires_at=_coerce_exp_datetime(payload.get("exp")),
            )
    except JWTError:
        pass
    return {"message": "Logged out successfully"}


@router.post("/auth/forgot-password", dependencies=[Depends(rate_limit_auth)])
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Send a password reset email if the user exists."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token_hash = _hash_reset_token(token)
        user.reset_token_expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.password_reset_token_expire_minutes
        )
        await db.commit()
        reset_link = f"{settings.frontend_base_url}/reset-password?token={token}"
        body = (
            "You requested a password reset for MedMemory.\n\n"
            f"Reset link: {reset_link}\n\n"
            "If you did not request this, you can ignore this message."
        )
        send_email([user.email], "MedMemory password reset", body)

    return {"message": "If the email exists, a reset link has been sent."}


@router.post("/auth/reset-password", dependencies=[Depends(rate_limit_auth)])
async def reset_password(
    payload: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Reset user password using a reset token."""
    token_hash = _hash_reset_token(payload.token)
    result = await db.execute(select(User).where(User.reset_token_hash == token_hash))
    user = result.scalar_one_or_none()
    if not user or not user.reset_token_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )
    if user.reset_token_expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )

    user.hashed_password = get_password_hash(payload.new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    await db.commit()

    return {"message": "Password updated successfully."}
