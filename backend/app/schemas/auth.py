from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserSignUp(BaseModel):
    """Schema for user signup."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ..., min_length=8, description="User password (minimum 8 characters)"
    )
    full_name: str = Field(
        ..., min_length=1, max_length=255, description="User full name"
    )


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    """Schema for authentication token response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry in seconds")
    user_id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email")


class MobileTokenRequest(BaseModel):
    """Request a short-lived patient-scoped mobile token."""

    patient_id: int = Field(..., ge=1, description="Patient ID the mobile token is bound to")
    scopes: list[str] = Field(
        default_factory=lambda: ["chat", "records", "documents", "apple_health"],
        description="Allowed scopes for the mobile patient token",
    )


class MobileTokenResponse(BaseModel):
    """Response for patient-scoped mobile token issuance."""

    access_token: str = Field(..., description="Short-lived patient-scoped JWT access token")
    refresh_token: str = Field(..., description="Patient-scoped JWT refresh token for mobile")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiry in seconds")
    patient_id: int = Field(..., description="Patient ID bound to the token")
    scopes: list[str] = Field(..., description="Scopes embedded in the token")


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""

    refresh_token: str = Field(..., description="Refresh token")


class UserResponse(BaseModel):
    """Schema for user response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    is_active: bool


class ForgotPasswordRequest(BaseModel):
    """Request to start password reset."""

    email: EmailStr = Field(..., description="User email address")


class ResetPasswordRequest(BaseModel):
    """Request to reset password."""

    token: str = Field(..., min_length=8, description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")
