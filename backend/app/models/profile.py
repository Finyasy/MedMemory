"""Profile-related models for comprehensive health data."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.patient import Patient


class PatientEmergencyInfo(Base):
    """Emergency information for a patient."""

    __tablename__ = "patient_emergency_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), unique=True
    )
    medical_alert: Mapped[str | None] = mapped_column(Text, nullable=True)
    organ_donor: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    dnr_status: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    preferred_hospital: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    patient: Mapped["Patient"] = relationship(back_populates="emergency_info")


class EmergencyContact(Base):
    """Emergency contact for a patient."""

    __tablename__ = "emergency_contacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_relationship: Mapped[str] = mapped_column(
        "relationship", String(50), nullable=False
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    priority_order: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient: Mapped["Patient"] = relationship(back_populates="emergency_contacts")


class PatientAllergy(Base):
    """Allergy record for a patient."""

    __tablename__ = "patient_allergies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    allergen: Mapped[str] = mapped_column(String(255), nullable=False)
    allergy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    reaction: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    patient: Mapped["Patient"] = relationship(back_populates="allergies_list")


class PatientCondition(Base):
    """Chronic condition record for a patient."""

    __tablename__ = "patient_conditions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    condition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    icd_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    diagnosed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    treating_physician: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    patient: Mapped["Patient"] = relationship(back_populates="conditions_list")


class PatientProvider(Base):
    """Healthcare provider for a patient."""

    __tablename__ = "patient_providers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    specialty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    clinic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fax: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient: Mapped["Patient"] = relationship(back_populates="providers")


class PatientLifestyle(Base):
    """Lifestyle factors for a patient."""

    __tablename__ = "patient_lifestyle"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), unique=True
    )
    smoking_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    smoking_frequency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    alcohol_use: Mapped[str | None] = mapped_column(String(20), nullable=True)
    exercise_frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    diet_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sleep_hours: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stress_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    patient: Mapped["Patient"] = relationship(back_populates="lifestyle")


class PatientInsurance(Base):
    """Insurance information for a patient."""

    __tablename__ = "patient_insurance"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    provider_name: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    group_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subscriber_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscriber_dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    relationship_to_subscriber: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient: Mapped["Patient"] = relationship(back_populates="insurance_list")


class FamilyHistory(Base):
    """Family medical history for a patient."""

    __tablename__ = "family_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    relation: Mapped[str] = mapped_column(String(50), nullable=False)
    condition: Mapped[str] = mapped_column(String(255), nullable=False)
    age_of_onset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_deceased: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient: Mapped["Patient"] = relationship(back_populates="family_history_list")


class PatientVaccination(Base):
    """Vaccination record for a patient."""

    __tablename__ = "patient_vaccinations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    vaccine_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dose_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_administered: Mapped[date] = mapped_column(Date, nullable=False)
    administered_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lot_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    site: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reaction: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient: Mapped["Patient"] = relationship(back_populates="vaccinations")


class GrowthMeasurement(Base):
    """Growth measurement for a patient (typically children)."""

    __tablename__ = "growth_measurements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    measurement_date: Mapped[date] = mapped_column(Date, nullable=False)
    age_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    head_circumference_cm: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    height_percentile: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_percentile: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bmi: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    bmi_percentile: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient: Mapped["Patient"] = relationship(back_populates="growth_measurements")


class PatientRelationship(Base):
    """Relationship between caretaker and dependent patients."""

    __tablename__ = "patient_relationships"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    caretaker_patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    dependent_patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_primary_caretaker: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=True)
    can_share: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    caretaker: Mapped["Patient"] = relationship(
        foreign_keys=[caretaker_patient_id], back_populates="dependents"
    )
    dependent: Mapped["Patient"] = relationship(
        foreign_keys=[dependent_patient_id], back_populates="caretakers"
    )

    __table_args__ = (UniqueConstraint("caretaker_patient_id", "dependent_patient_id"),)
