from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.encounter import Encounter
    from app.models.lab_result import LabResult
    from app.models.medication import Medication
    from app.models.document import Document
    from app.models.memory_chunk import MemoryChunk
    from app.models.record import Record
    from app.models.record import Record


class Patient(Base, TimestampMixin):
    """Patient model storing core demographic and identification data."""
    
    __tablename__ = "patients"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    external_id: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, index=True, nullable=True,
        comment="External patient ID from source system"
    )
    
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    blood_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    allergies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    medical_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
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
    records: Mapped[list["Record"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    
    @property
    def full_name(self) -> str:
        """Return the patient's full name."""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self) -> Optional[int]:
        """Calculate the patient's age."""
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
    def __repr__(self) -> str:
        return f"<Patient(id={self.id}, name='{self.full_name}')>"
