"""Document management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Document, MemoryChunk
from app.schemas.document import (
    BatchProcessResponse,
    DocumentDetail,
    DocumentProcessRequest,
    DocumentProcessResponse,
    DocumentResponse,
)
from app.services.documents import DocumentProcessor, DocumentUploadService

router = APIRouter(prefix="/documents", tags=["Documents"])


# ============================================
# Document Upload
# ============================================

@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    patient_id: int = Form(...),
    document_type: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a new document for a patient.
    
    Supported file types: PDF, PNG, JPEG, TIFF, DOCX, TXT
    Maximum file size: 50MB
    """
    service = DocumentUploadService(db)
    
    try:
        document = await service.upload_document(
            file=file,
            patient_id=patient_id,
            document_type=document_type,
            title=title,
            description=description,
            category=category,
        )
        return DocumentResponse.model_validate(document)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Document Processing
# ============================================

@router.post("/{document_id}/process", response_model=DocumentProcessResponse)
async def process_document(
    document_id: int,
    request: DocumentProcessRequest = DocumentProcessRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Process a document: extract text and create memory chunks.
    
    This extracts text from the document using appropriate methods:
    - PDFs: Direct text extraction + OCR for image pages
    - Images: OCR
    - DOCX: Text extraction
    
    Memory chunks are created for semantic search in later phases.
    """
    processor = DocumentProcessor(db)
    
    try:
        document = await processor.process_document(
            document_id=document_id,
            create_memory_chunks=request.create_memory_chunks,
        )
        
        # Count memory chunks created
        result = await db.execute(
            select(MemoryChunk).where(MemoryChunk.document_id == document_id)
        )
        chunks = result.scalars().all()
        
        return DocumentProcessResponse(
            document_id=document.id,
            status=document.processing_status,
            page_count=document.page_count,
            chunks_created=len(chunks),
            text_preview=document.extracted_text[:500] if document.extracted_text else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/process/pending", response_model=BatchProcessResponse)
async def process_pending_documents(
    db: AsyncSession = Depends(get_db),
):
    """Process all pending documents.
    
    Useful for batch processing after uploading multiple documents.
    """
    processor = DocumentProcessor(db)
    stats = await processor.process_all_pending()
    return BatchProcessResponse(**stats)


@router.post("/{document_id}/reprocess", response_model=DocumentProcessResponse)
async def reprocess_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Reprocess a document (delete existing chunks and extract again)."""
    processor = DocumentProcessor(db)
    
    try:
        document = await processor.reprocess_document(document_id)
        
        result = await db.execute(
            select(MemoryChunk).where(MemoryChunk.document_id == document_id)
        )
        chunks = result.scalars().all()
        
        return DocumentProcessResponse(
            document_id=document.id,
            status=document.processing_status,
            page_count=document.page_count,
            chunks_created=len(chunks),
            text_preview=document.extracted_text[:500] if document.extracted_text else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================
# Document Retrieval
# ============================================

@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    patient_id: Optional[int] = None,
    document_type: Optional[str] = None,
    processed_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List documents with optional filtering."""
    query = select(Document)
    
    if patient_id:
        query = query.where(Document.patient_id == patient_id)
    
    if document_type:
        query = query.where(Document.document_type == document_type)
    
    if processed_only:
        query = query.where(Document.is_processed == True)
    
    query = query.order_by(Document.received_date.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    documents = result.scalars().all()
    
    return [DocumentResponse.model_validate(doc) for doc in documents]


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get document details including extracted text."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentDetail.model_validate(document)


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Download the original document file."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return FileResponse(
        path=document.file_path,
        filename=document.original_filename,
        media_type=document.mime_type,
    )


@router.get("/{document_id}/text")
async def get_document_text(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get just the extracted text from a document."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not document.is_processed:
        raise HTTPException(
            status_code=400,
            detail="Document has not been processed. Call /process endpoint first."
        )
    
    return {
        "document_id": document.id,
        "extracted_text": document.extracted_text,
        "page_count": document.page_count,
    }


# ============================================
# Document Deletion
# ============================================

@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and its associated file and memory chunks."""
    service = DocumentUploadService(db)
    
    # Delete memory chunks first
    await db.execute(
        MemoryChunk.__table__.delete().where(MemoryChunk.document_id == document_id)
    )
    
    # Delete document
    deleted = await service.delete_document(document_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")


# ============================================
# Patient Documents
# ============================================

@router.get("/patient/{patient_id}", response_model=list[DocumentResponse])
async def get_patient_documents(
    patient_id: int,
    document_type: Optional[str] = None,
    processed_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Get all documents for a specific patient."""
    service = DocumentUploadService(db)
    
    documents = await service.get_patient_documents(
        patient_id=patient_id,
        document_type=document_type,
        processed_only=processed_only,
    )
    
    return [DocumentResponse.model_validate(doc) for doc in documents]
