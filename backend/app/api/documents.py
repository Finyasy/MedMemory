"""Document management API endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import load_only
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_patient_for_user
from app.database import get_db
from app.config import settings
from app.models import Document, MemoryChunk, Patient, User
from app.schemas.document import (
    BatchProcessResponse,
    DocumentDetail,
    DocumentProcessRequest,
    DocumentProcessResponse,
    DocumentResponse,
    OcrRefinementResponse,
)
from app.services.documents import DocumentProcessor, DocumentUploadService
from app.utils.cache import clear_cache, get_cached, set_cached

router = APIRouter(prefix="/documents", tags=["Documents"])


async def _get_document_for_user(
    document_id: int,
    db: AsyncSession,
    current_user: User,
) -> Document:
    result = await db.execute(
        select(Document)
        .join(Patient, Document.patient_id == Patient.id)
        .where(Document.id == document_id, Patient.user_id == current_user.id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


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
    current_user: User = Depends(get_authenticated_user),
):
    """Upload a new document for a patient.
    
    Supported file types: PDF, PNG, JPEG, TIFF, DOCX, TXT
    Maximum file size: 50MB
    """
    await get_patient_for_user(patient_id=patient_id, db=db, current_user=current_user)
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
    finally:
        await clear_cache(f"documents:{current_user.id}:")


# ============================================
# Document Processing
# ============================================

@router.post("/{document_id}/process", response_model=DocumentProcessResponse)
async def process_document(
    document_id: int,
    request: DocumentProcessRequest = DocumentProcessRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Process a document: extract text and create memory chunks.
    
    This extracts text from the document using appropriate methods:
    - PDFs: Direct text extraction + OCR for image pages
    - Images: OCR
    - DOCX: Text extraction
    
    Memory chunks are created for semantic search in later phases.
    """
    await _get_document_for_user(document_id=document_id, db=db, current_user=current_user)
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
    finally:
        await clear_cache(f"documents:{current_user.id}:")


@router.post("/process/pending", response_model=BatchProcessResponse)
async def process_pending_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Process all pending documents.
    
    Useful for batch processing after uploading multiple documents.
    """
    processor = DocumentProcessor(db)
    result = await db.execute(
        select(Document)
        .join(Patient, Document.patient_id == Patient.id)
        .where(Document.processing_status == "pending", Patient.user_id == current_user.id)
    )
    documents = result.scalars().all()

    stats = {
        "total": len(documents),
        "processed": 0,
        "failed": 0,
        "errors": [],
    }

    for doc in documents:
        try:
            await processor.process_document(doc.id)
            stats["processed"] += 1
        except Exception as exc:  # noqa: BLE001 - report errors per document
            stats["failed"] += 1
            stats["errors"].append(f"Document {doc.id}: {str(exc)}")

    return BatchProcessResponse(**stats)


@router.post("/{document_id}/reprocess", response_model=DocumentProcessResponse)
async def reprocess_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Reprocess a document (delete existing chunks and extract again)."""
    await _get_document_for_user(document_id=document_id, db=db, current_user=current_user)
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
    finally:
        await clear_cache(f"documents:{current_user.id}:")


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
    current_user: User = Depends(get_authenticated_user),
):
    """List documents with optional filtering."""
    cache_key = f"documents:{current_user.id}:{patient_id or 'all'}:{document_type or ''}:{processed_only}:{skip}:{limit}"
    cached = await get_cached(cache_key)
    if cached is not None:
        return cached
    query = (
        select(Document)
        .options(
            load_only(
                Document.id,
                Document.patient_id,
                Document.filename,
                Document.original_filename,
                Document.file_size,
                Document.mime_type,
                Document.document_type,
                Document.category,
                Document.title,
                Document.description,
                Document.document_date,
                Document.received_date,
                Document.processing_status,
                Document.is_processed,
                Document.processed_at,
                Document.page_count,
                Document.created_at,
            )
        )
        .join(Patient, Document.patient_id == Patient.id)
        .where(Patient.user_id == current_user.id)
    )
    
    if patient_id:
        await get_patient_for_user(patient_id=patient_id, db=db, current_user=current_user)
        query = query.where(Document.patient_id == patient_id)
    
    if document_type:
        query = query.where(Document.document_type == document_type)
    
    if processed_only:
        query = query.where(Document.is_processed == True)
    
    query = query.order_by(Document.received_date.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    documents = result.scalars().all()

    response = [DocumentResponse.model_validate(doc) for doc in documents]
    await set_cached(cache_key, response, ttl_seconds=settings.response_cache_ttl_seconds)
    return response


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get document details including extracted text."""
    document = await _get_document_for_user(document_id=document_id, db=db, current_user=current_user)
    
    return DocumentDetail.model_validate(document)


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Download the original document file."""
    document = await _get_document_for_user(document_id=document_id, db=db, current_user=current_user)
    
    return FileResponse(
        path=document.file_path,
        filename=document.original_filename,
        media_type=document.mime_type,
    )


@router.get("/{document_id}/text")
async def get_document_text(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get just the extracted text from a document."""
    document = await _get_document_for_user(document_id=document_id, db=db, current_user=current_user)
    
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


@router.get("/{document_id}/ocr", response_model=OcrRefinementResponse)
async def get_document_ocr(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get OCR refinement output for a document."""
    document = await _get_document_for_user(document_id=document_id, db=db, current_user=current_user)

    ocr_entities: dict = {}
    if document.ocr_entities:
        try:
            ocr_entities = json.loads(document.ocr_entities)
        except json.JSONDecodeError:
            ocr_entities = {}

    return OcrRefinementResponse(
        document_id=document.id,
        ocr_language=document.ocr_language,
        ocr_confidence=document.ocr_confidence,
        ocr_text_raw=document.ocr_text_raw,
        ocr_text_cleaned=document.ocr_text_cleaned,
        ocr_entities=ocr_entities,
        used_ocr=bool(document.ocr_text_raw),
    )


# ============================================
# Document Deletion
# ============================================

@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete a document and its associated file and memory chunks."""
    service = DocumentUploadService(db)
    
    # Delete memory chunks first
    await db.execute(
        MemoryChunk.__table__.delete().where(MemoryChunk.document_id == document_id)
    )
    
    # Delete document
    await _get_document_for_user(document_id=document_id, db=db, current_user=current_user)
    deleted = await service.delete_document(document_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    await clear_cache(f"documents:{current_user.id}:")


# ============================================
# Patient Documents
# ============================================

@router.get("/patient/{patient_id}", response_model=list[DocumentResponse])
async def get_patient_documents(
    patient_id: int,
    document_type: Optional[str] = None,
    processed_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get all documents for a specific patient."""
    await get_patient_for_user(patient_id=patient_id, db=db, current_user=current_user)
    service = DocumentUploadService(db)
    
    documents = await service.get_patient_documents(
        patient_id=patient_id,
        document_type=document_type,
        processed_only=processed_only,
    )
    
    return [DocumentResponse.model_validate(doc) for doc in documents]
