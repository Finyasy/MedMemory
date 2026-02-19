from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clinician_profile import ClinicianProfile
    from app.models.patient import Patient
    from app.models.patient_access_grant import PatientAccessGrant


class UserRole(StrEnum):
    patient = "patient"
    clinician = "clinician"
    staff = "staff"
    admin = "admin"


class User(Base, TimestampMixin):
    """User model for authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="User email address",
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="BCrypt hashed password"
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.patient.value,
        server_default="patient",
        comment="User role: patient, clinician, staff, admin",
    )

    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    reset_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    patients: Mapped[list["Patient"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    clinician_profile: Mapped[Optional["ClinicianProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    access_grants_as_clinician: Mapped[list["PatientAccessGrant"]] = relationship(
        foreign_keys="PatientAccessGrant.clinician_user_id",
        back_populates="clinician",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"
