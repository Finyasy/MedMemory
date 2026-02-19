from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.patient import Patient


class Encounter(Base, TimestampMixin):
    """Encounter model for storing medical visits and appointments."""

    __tablename__ = "encounters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    encounter_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="e.g., office_visit, emergency, telehealth, inpatient",
    )

    encounter_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    facility: Mapped[str | None] = mapped_column(String(200), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)

    provider_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider_specialty: Mapped[str | None] = mapped_column(String(100), nullable=True)

    chief_complaint: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_for_visit: Mapped[str | None] = mapped_column(Text, nullable=True)

    diagnoses: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON array of diagnosis codes/descriptions"
    )
    assessment: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up: Mapped[str | None] = mapped_column(Text, nullable=True)

    subjective: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Patient's reported symptoms/history"
    )
    objective: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Physical exam findings, vitals"
    )
    clinical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    vital_blood_pressure: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vital_heart_rate: Mapped[int | None] = mapped_column(nullable=True)
    vital_temperature: Mapped[float | None] = mapped_column(nullable=True)
    vital_weight: Mapped[float | None] = mapped_column(nullable=True)
    vital_height: Mapped[float | None] = mapped_column(nullable=True)
    vital_bmi: Mapped[float | None] = mapped_column(nullable=True)
    vital_oxygen_saturation: Mapped[float | None] = mapped_column(nullable=True)

    status: Mapped[str] = mapped_column(
        String(50),
        default="completed",
        comment="scheduled, in-progress, completed, cancelled",
    )

    source_system: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="encounters")

    def __repr__(self) -> str:
        return f"<Encounter(id={self.id}, type='{self.encounter_type}', date={self.encounter_date})>"
