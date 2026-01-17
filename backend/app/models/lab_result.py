from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.patient import Patient


class LabResult(Base, TimestampMixin):
    """Lab result model for storing laboratory test data."""
    
    __tablename__ = "lab_results"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    test_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    test_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="LOINC or local test code"
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="e.g., Hematology, Chemistry, Microbiology"
    )
    
    value: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    numeric_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="normal, abnormal, critical"
    )
    is_abnormal: Mapped[bool] = mapped_column(default=False)
    
    collected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resulted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ordering_provider: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    performing_lab: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    source_system: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    patient: Mapped["Patient"] = relationship(back_populates="lab_results")

    __table_args__ = (
        Index("ix_lab_results_patient_collected", "patient_id", "collected_at"),
    )
    
    def __repr__(self) -> str:
        return f"<LabResult(id={self.id}, test='{self.test_name}', value='{self.value}')>"
