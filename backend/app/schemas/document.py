"""Pydantic schemas for Document API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentUpload(BaseModel):
    """Schema for document upload metadata."""
    
    patient_id: int
    document_type: Optional[str] = Field(None, max_length=50)
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    document_date: Optional[datetime] = None
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[list[str]] = None


class DocumentResponse(BaseModel):
    """Response schema for document."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    patient_id: int
    filename: str
    original_filename: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    document_type: str
    category: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    document_date: Optional[datetime] = None
    received_date: datetime
    processing_status: str
    is_processed: bool
    processed_at: Optional[datetime] = None
    page_count: Optional[int] = None
    created_at: datetime


class DocumentDetail(DocumentResponse):
    """Detailed document response including extracted text."""
    
    extracted_text: Optional[str] = None
    processing_error: Optional[str] = None
    ocr_confidence: Optional[float] = None
    author: Optional[str] = None
    facility: Optional[str] = None


class DocumentProcessRequest(BaseModel):
    """Request to process a document."""
    
    create_memory_chunks: bool = True


class DocumentProcessResponse(BaseModel):
    """Response after document processing."""
    
    document_id: int
    status: str
    page_count: Optional[int] = None
    chunks_created: int = 0
    text_preview: Optional[str] = Field(None, description="First 500 chars of extracted text")


class BatchProcessResponse(BaseModel):
    """Response for batch document processing."""
    
    total: int
    processed: int
    failed: int
    errors: list[str] = []
