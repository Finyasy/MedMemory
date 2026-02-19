"""Pydantic schemas for Document API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentUpload(BaseModel):
    """Schema for document upload metadata."""

    patient_id: int
    document_type: str | None = Field(None, max_length=50)
    title: str | None = Field(None, max_length=300)
    description: str | None = None
    document_date: datetime | None = None
    category: str | None = Field(None, max_length=100)
    tags: list[str] | None = None


class DocumentResponse(BaseModel):
    """Response schema for document."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    filename: str
    original_filename: str
    file_size: int | None = None
    mime_type: str | None = None
    document_type: str
    category: str | None = None
    title: str | None = None
    description: str | None = None
    document_date: datetime | None = None
    received_date: datetime
    processing_status: str
    is_processed: bool
    processed_at: datetime | None = None
    page_count: int | None = None
    created_at: datetime


class DocumentDetail(DocumentResponse):
    """Detailed document response including extracted text."""

    extracted_text: str | None = None
    processing_error: str | None = None
    ocr_confidence: float | None = None
    ocr_language: str | None = None
    ocr_text_raw: str | None = None
    ocr_text_cleaned: str | None = None
    ocr_entities: str | None = None
    author: str | None = None
    facility: str | None = None


class DocumentProcessRequest(BaseModel):
    """Request to process a document."""

    create_memory_chunks: bool = True


class DocumentProcessResponse(BaseModel):
    """Response after document processing."""

    document_id: int
    status: str
    page_count: int | None = None
    chunks_created: int = 0
    text_preview: str | None = Field(
        None, description="First 500 chars of extracted text"
    )


class BatchProcessResponse(BaseModel):
    """Response for batch document processing."""

    total: int
    processed: int
    failed: int
    errors: list[str] = []


class OcrRefinementResponse(BaseModel):
    """OCR refinement output for a document."""

    document_id: int
    ocr_language: str | None = None
    ocr_confidence: float | None = None
    ocr_text_raw: str | None = None
    ocr_text_cleaned: str | None = None
    ocr_entities: dict = Field(default_factory=dict)
    used_ocr: bool = False
