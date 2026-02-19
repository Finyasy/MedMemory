from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.encounter import Encounter
    from app.models.lab_result import LabResult
    from app.models.medication import Medication
    from app.models.memory_chunk import MemoryChunk
    from app.models.patient_access_grant import PatientAccessGrant
    from app.models.profile import (
        EmergencyContact,
        FamilyHistory,
        GrowthMeasurement,
        PatientAllergy,
        PatientCondition,
        PatientEmergencyInfo,
        PatientInsurance,
        PatientLifestyle,
        PatientProvider,
        PatientRelationship,
        PatientVaccination,
    )
    from app.models.record import Record
    from app.models.user import User


class Patient(Base, TimestampMixin):
    """Patient model storing core demographic and identification data."""

    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Owning user for this patient",
    )

    external_id: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=True,
        comment="External patient ID from source system",
    )

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(20), nullable=True)

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    blood_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    medical_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)

    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(
        String(10), default="en", nullable=True
    )
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    profile_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_dependent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    profile_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # Core relationships
    lab_results: Mapped[list["LabResult"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    medications: Mapped[list["Medication"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    encounters: Mapped[list["Encounter"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    memory_chunks: Mapped[list["MemoryChunk"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    records: Mapped[list["Record"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    user: Mapped["User"] = relationship(back_populates="patients")
    access_grants: Mapped[list["PatientAccessGrant"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )

    # Profile relationships
    emergency_info: Mapped[Optional["PatientEmergencyInfo"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", uselist=False
    )
    emergency_contacts: Mapped[list["EmergencyContact"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    allergies_list: Mapped[list["PatientAllergy"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    conditions_list: Mapped[list["PatientCondition"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    providers: Mapped[list["PatientProvider"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    lifestyle: Mapped[Optional["PatientLifestyle"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", uselist=False
    )
    insurance_list: Mapped[list["PatientInsurance"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    family_history_list: Mapped[list["FamilyHistory"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    vaccinations: Mapped[list["PatientVaccination"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    growth_measurements: Mapped[list["GrowthMeasurement"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )

    # Dependent relationships
    dependents: Mapped[list["PatientRelationship"]] = relationship(
        foreign_keys="PatientRelationship.caretaker_patient_id",
        back_populates="caretaker",
        cascade="all, delete-orphan",
    )
    caretakers: Mapped[list["PatientRelationship"]] = relationship(
        foreign_keys="PatientRelationship.dependent_patient_id",
        back_populates="dependent",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_patients_user_last_first", "user_id", "last_name", "first_name"),
    )

    @property
    def full_name(self) -> str:
        """Return the patient's full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int | None:
        """Calculate the patient's age."""
        if self.date_of_birth:
            today = date.today()
            return (
                today.year
                - self.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (self.date_of_birth.month, self.date_of_birth.day)
                )
            )
        return None

    def __repr__(self) -> str:
        return f"<Patient(id={self.id}, name='{self.full_name}')>"
