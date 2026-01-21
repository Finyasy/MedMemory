from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.patient import Patient


class Document(Base, TimestampMixin):
    """Document model for storing uploaded medical documents."""
    
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True,
        comment="SHA-256 hash for deduplication"
    )
    
    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="e.g., lab_report, imaging, discharge_summary, prescription"
    )
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    document_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Date the document was created/signed"
    )
    received_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="Date the document was uploaded"
    )
    
    processing_status: Mapped[str] = mapped_column(
        String(50), default="pending",
        comment="pending, processing, completed, failed"
    )
    is_processed: Mapped[bool] = mapped_column(default=False, index=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    
    ocr_confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    ocr_language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    ocr_text_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_text_cleaned: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_entities: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON payload with extracted entities from OCR text",
    )
    
    author: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    facility: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="JSON array of tags"
    )
    
    source_system: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    patient: Mapped["Patient"] = relationship(back_populates="documents")

    __table_args__ = (
        Index("ix_documents_patient_received", "patient_id", "received_date"),
    )
    
    def __repr__(self) -> str:
        return f"<Document(id={self.id}, type='{self.document_type}', filename='{self.filename}')>"
