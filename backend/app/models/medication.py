from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.patient import Patient


class Medication(Base, TimestampMixin):
    """Medication model for storing prescription and medication data."""
    
    __tablename__ = "medications"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    generic_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    drug_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="RxNorm, NDC, or other drug code"
    )
    drug_class: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="e.g., Antibiotic, Antihypertensive"
    )
    
    dosage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dosage_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dosage_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    frequency: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="e.g., twice daily, every 8 hours"
    )
    route: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="e.g., oral, IV, topical"
    )
    
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    prescribed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="active, completed, discontinued, on-hold"
    )
    discontinue_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    prescriber: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    pharmacy: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    quantity: Mapped[Optional[int]] = mapped_column(nullable=True)
    refills_remaining: Mapped[Optional[int]] = mapped_column(nullable=True)
    
    indication: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Why the medication was prescribed"
    )
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    source_system: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    patient: Mapped["Patient"] = relationship(back_populates="medications")

    __table_args__ = (
        Index("ix_medications_patient_prescribed", "patient_id", "prescribed_at"),
    )
    
    @property
    def is_current(self) -> bool:
        """Check if medication is currently active."""
        if not self.is_active:
            return False
        today = date.today()
        if self.end_date and self.end_date < today:
            return False
        return True
    
    def __repr__(self) -> str:
        return f"<Medication(id={self.id}, name='{self.name}', active={self.is_active})>"
