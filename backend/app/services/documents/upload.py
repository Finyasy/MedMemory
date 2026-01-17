"""Document upload and management service."""

import hashlib
import os
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import UploadFile
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Document, Patient


class DocumentUploadService:
    """Service for handling document uploads and storage.
    
    Handles file validation, storage, deduplication, and
    database record creation for uploaded documents.
    """
    
    # Document type mappings based on MIME types
    MIME_TYPE_MAPPING = {
        "application/pdf": "pdf",
        "image/png": "image",
        "image/jpeg": "image",
        "image/jpg": "image",
        "image/tiff": "image",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "text/plain": "text",
    }
    
    # Suggested document types based on filename patterns
    DOCUMENT_TYPE_PATTERNS = {
        "lab": "lab_report",
        "result": "lab_report",
        "blood": "lab_report",
        "xray": "imaging",
        "ct": "imaging",
        "mri": "imaging",
        "scan": "imaging",
        "ultrasound": "imaging",
        "discharge": "discharge_summary",
        "summary": "discharge_summary",
        "prescription": "prescription",
        "rx": "prescription",
        "referral": "referral",
        "consult": "consultation",
        "note": "clinical_note",
        "progress": "clinical_note",
        "insurance": "insurance",
        "claim": "insurance",
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.upload_dir = Path(settings.upload_dir)
        self.max_size = settings.max_upload_size
        self.allowed_extensions = settings.allowed_extensions
    
    async def upload_document(
        self,
        file: UploadFile,
        patient_id: int,
        document_type: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        document_date: Optional[datetime] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> Document:
        """Upload and store a document.
        
        Args:
            file: Uploaded file
            patient_id: ID of the patient this document belongs to
            document_type: Type of document (auto-detected if not provided)
            title: Document title (uses filename if not provided)
            description: Document description
            document_date: Date the document was created
            category: Document category
            tags: List of tags for the document
            
        Returns:
            Created Document model instance
            
        Raises:
            ValueError: If file validation fails
        """
        # Validate patient exists
        patient = await self._get_patient(patient_id)
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")
        
        # Validate file
        await self._validate_file(file)
        
        # Read file content and compute hash
        content = await file.read()
        file_hash = self._compute_hash(content)
        
        # Check for duplicate
        existing = await self._check_duplicate(file_hash)
        if existing:
            raise ValueError(
                f"Document already exists with ID {existing.id}. "
                "Use the existing document or delete it first."
            )
        
        # Generate storage path
        file_ext = self._get_extension(file.filename or "unknown")
        stored_filename = f"{uuid.uuid4()}{file_ext}"
        
        # Create patient directory if needed
        patient_dir = self.upload_dir / str(patient_id)
        patient_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = patient_dir / stored_filename
        
        # Save file
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        
        # Auto-detect document type if not provided
        if not document_type:
            document_type = self._detect_document_type(
                filename=file.filename or "",
                mime_type=file.content_type,
            )
        
        # Create database record
        document = Document(
            patient_id=patient_id,
            filename=stored_filename,
            original_filename=file.filename or "unknown",
            file_path=str(file_path),
            file_size=len(content),
            mime_type=file.content_type,
            file_hash=file_hash,
            document_type=document_type,
            category=category,
            title=title or file.filename,
            description=description,
            document_date=document_date,
            received_date=datetime.now(timezone.utc),
            processing_status="pending",
            is_processed=False,
            tags=",".join(tags) if tags else None,
        )
        
        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)
        
        return document
    
    async def get_document(self, document_id: int) -> Optional[Document]:
        """Get a document by ID."""
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()
    
    async def get_patient_documents(
        self,
        patient_id: int,
        document_type: Optional[str] = None,
        processed_only: bool = False,
    ) -> list[Document]:
        """Get all documents for a patient."""
        query = select(Document).where(Document.patient_id == patient_id)
        
        if document_type:
            query = query.where(Document.document_type == document_type)
        
        if processed_only:
            query = query.where(Document.is_processed == True)
        
        query = query.order_by(Document.received_date.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def delete_document(self, document_id: int) -> bool:
        """Delete a document and its file."""
        document = await self.get_document(document_id)
        if not document:
            return False
        
        # Delete file
        try:
            file_path = Path(document.file_path)
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass  # Continue even if file deletion fails
        
        # Delete database record
        await self.db.delete(document)
        return True
    
    async def update_processing_status(
        self,
        document_id: int,
        status: str,
        extracted_text: Optional[str] = None,
        page_count: Optional[int] = None,
        error: Optional[str] = None,
    ) -> Document:
        """Update document processing status."""
        document = await self.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        document.processing_status = status
        
        if status == "completed":
            document.is_processed = True
            document.processed_at = datetime.now(timezone.utc)
            document.extracted_text = extracted_text
            document.page_count = page_count
        elif status == "failed":
            document.processing_error = error
        
        await self.db.flush()
        return document
    
    async def _get_patient(self, patient_id: int) -> Optional[Patient]:
        """Get patient by ID."""
        result = await self.db.execute(
            select(Patient).where(Patient.id == patient_id)
        )
        return result.scalar_one_or_none()
    
    async def _validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file."""
        # Check filename
        if not file.filename:
            raise ValueError("File must have a filename")
        
        # Check extension
        ext = self._get_extension(file.filename)
        if ext.lower() not in self.allowed_extensions:
            raise ValueError(
                f"File type '{ext}' not allowed. "
                f"Allowed types: {', '.join(self.allowed_extensions)}"
            )

        if file.content_type and file.content_type not in settings.allowed_mime_types:
            raise ValueError(
                f"MIME type '{file.content_type}' not allowed. "
                f"Allowed types: {', '.join(settings.allowed_mime_types)}"
            )
        
        # Check size (need to read to check, then seek back)
        content = await file.read()
        await file.seek(0)
        
        if len(content) > self.max_size:
            raise ValueError(
                f"File too large ({len(content)} bytes). "
                f"Maximum size: {self.max_size} bytes"
            )

        if file.content_type == "application/pdf" and not content.startswith(b"%PDF"):
            raise ValueError("Invalid PDF file header")
        if file.content_type in {"image/png", "image/jpeg", "image/jpg", "image/tiff"}:
            try:
                Image.open(BytesIO(content)).verify()
            except Exception:
                raise ValueError("Invalid image file content")
        if file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            if not content.startswith(b"PK"):
                raise ValueError("Invalid DOCX file header")
        if file.content_type == "text/plain":
            if b"\x00" in content:
                raise ValueError("Invalid text file content")
    
    def _get_extension(self, filename: str) -> str:
        """Get file extension from filename."""
        return os.path.splitext(filename)[1].lower()
    
    def _compute_hash(self, content: bytes) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(content).hexdigest()
    
    async def _check_duplicate(self, file_hash: str) -> Optional[Document]:
        """Check if a document with the same hash exists."""
        result = await self.db.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        return result.scalar_one_or_none()
    
    def _detect_document_type(
        self,
        filename: str,
        mime_type: Optional[str],
    ) -> str:
        """Auto-detect document type from filename and MIME type."""
        filename_lower = filename.lower()
        
        # Check filename patterns
        for pattern, doc_type in self.DOCUMENT_TYPE_PATTERNS.items():
            if pattern in filename_lower:
                return doc_type
        
        # Fall back to MIME type mapping
        if mime_type and mime_type in self.MIME_TYPE_MAPPING:
            base_type = self.MIME_TYPE_MAPPING[mime_type]
            if base_type == "pdf":
                return "medical_record"
            elif base_type == "image":
                return "imaging"
        
        return "other"
