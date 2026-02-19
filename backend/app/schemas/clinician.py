"""Pydantic schemas for Clinician and Access Grant APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ----- Clinician auth & profile -----


class ClinicianSignUp(BaseModel):
    """Schema for clinician signup (creates user with role=clinician + optional profile)."""

    email: EmailStr = Field(..., description="Clinician email")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    full_name: str = Field(..., min_length=1, max_length=255, description="Full name")
    registration_number: str = Field(
        ..., min_length=1, max_length=100, description="Registration number (mandatory)"
    )
    specialty: str | None = Field(None, max_length=255, description="Specialty")
    organization_name: str | None = Field(
        None, max_length=255, description="Organization"
    )
    phone: str | None = Field(None, max_length=50, description="Phone")
    address: str | None = Field(None, description="Address")


class ClinicianLogin(BaseModel):
    """Schema for clinician login (same as user login)."""

    email: EmailStr = Field(..., description="Clinician email")
    password: str = Field(..., description="Password")


class ClinicianProfileResponse(BaseModel):
    """Clinician profile response (user + profile fields)."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    full_name: str
    npi: str | None = None
    license_number: str | None = None
    specialty: str | None = None
    organization_name: str | None = None
    phone: str | None = None
    address: str | None = None
    verified_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ClinicianProfileUpdate(BaseModel):
    """Schema for updating clinician profile."""

    full_name: str | None = Field(None, min_length=1, max_length=255)
    npi: str | None = Field(None, max_length=20)
    license_number: str | None = Field(None, max_length=100)
    specialty: str | None = Field(None, max_length=255)
    organization_name: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    address: str | None = None


# ----- Access grants -----


class AccessRequestCreate(BaseModel):
    """Clinician requests access to a patient (creates grant with status=pending)."""

    patient_id: int = Field(..., description="Patient to request access to")
    scopes: str | None = Field(
        None,
        description="Comma-separated: documents, records, labs, medications, chat (default: all)",
    )
    expires_in_days: int | None = Field(
        None, ge=1, le=365, description="Access expiry in days"
    )


class AccessGrantResponse(BaseModel):
    """Single access grant response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    clinician_user_id: int
    status: str
    scopes: str
    granted_at: datetime | None = None
    expires_at: datetime | None = None
    granted_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime


class PatientWithGrant(BaseModel):
    """Patient summary with grant info (for clinician's patient list)."""

    patient_id: int
    patient_first_name: str
    patient_last_name: str
    patient_full_name: str
    grant_id: int
    grant_status: str
    grant_scopes: str
    granted_at: datetime | None = None
    expires_at: datetime | None = None


class PatientAccessGrantApprove(BaseModel):
    """Patient owner approves a pending grant."""

    grant_id: int = Field(..., description="Grant to approve")
    scopes: str | None = Field(
        None,
        description="Comma-separated scopes to grant (default: request's scopes)",
    )
    expires_in_days: int | None = Field(
        None, ge=1, le=365, description="Expiry in days"
    )


class PatientAccessRevoke(BaseModel):
    """Patient owner revokes a grant."""

    grant_id: int = Field(..., description="Grant to revoke")


class PatientAccessRequestItem(BaseModel):
    """Single access request/grant for patient's list (with clinician info)."""

    grant_id: int
    patient_id: int
    patient_name: str
    clinician_user_id: int
    clinician_name: str
    clinician_email: str
    status: str
    scopes: str
    created_at: datetime
