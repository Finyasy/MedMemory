from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.patient import Patient


class Record(Base, TimestampMixin):
    """Medical record model for storing general medical records.
    
    This is a flexible model for storing various types of medical records
    that don't fit into specific categories (labs, medications, encounters).
    """
    
    __tablename__ = "records"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    record_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="general", index=True
    )
    
    patient: Mapped["Patient"] = relationship(back_populates="records")
    
    def __repr__(self) -> str:
        return f"<Record(id={self.id}, patient_id={self.patient_id}, type='{self.record_type}')>"
