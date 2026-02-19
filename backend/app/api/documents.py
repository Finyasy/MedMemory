"""Document management API endpoints."""

import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.api.deps import get_authenticated_user, get_patient_for_user
from app.config import settings
from app.database import get_db
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
from app.services.llm import LLMService
from app.utils.cache import CacheKeys, clear_cache, get_cached, set_cached

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger("medmemory")


def _is_cxr_document(document: Document) -> bool:
    name = (document.original_filename or document.title or "").lower()
    return (
        document.document_type == "imaging"
        and (document.mime_type or "").startswith("image/")
        and any(token in name for token in ("cxr", "xray", "chest"))
    )


def _document_sort_date(document: Document) -> datetime:
    return document.document_date or document.received_date


def _format_doc_date(document: Document) -> str:
    return _document_sort_date(document).date().isoformat()


def _append_document_note(document: Document, note: str) -> None:
    if not note:
        return
    if document.description:
        document.description = f"{document.description}\n{note}"
    else:
        document.description = note


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


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    patient_id: int = Form(...),
    document_type: str | None = Form(None),
    title: str | None = Form(None),
    description: str | None = Form(None),
    category: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Upload a new document for a patient."""
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
        if _is_cxr_document(document):
            cxr_note = ""
            try:
                result = await db.execute(
                    select(Document).where(
                        Document.patient_id == patient_id,
                        Document.id != document.id,
                        Document.document_type == "imaging",
                    )
                )
                candidates = [
                    doc for doc in result.scalars().all() if _is_cxr_document(doc)
                ]
                if not candidates:
                    cxr_note = "Auto CXR comparison: no prior baseline image found."
                else:
                    current_date = _document_sort_date(document)
                    prior = max(
                        (
                            doc
                            for doc in candidates
                            if _document_sort_date(doc) <= current_date
                        ),
                        key=_document_sort_date,
                        default=None,
                    ) or max(candidates, key=_document_sort_date)
                    follow_up_date = _format_doc_date(document)
                    baseline_date = _format_doc_date(prior)
                    follow_up_bytes = Path(document.file_path).read_bytes()
                    baseline_bytes = Path(prior.file_path).read_bytes()
                    llm_service = LLMService.get_instance()
                    system_prompt = (
                        "You are a medical imaging assistant writing concise interval chest X-ray comparisons. "
                        "Use plain language, avoid speculation, and explicitly state if no clear interval change is seen."
                    )
                    prompt_text = (
                        "I am providing two Chest X-rays for the same patient.\n"
                        f"- The first image is the baseline scan from {baseline_date}.\n"
                        f"- The second image is the follow-up scan from {follow_up_date}.\n"
                        "Compare the second image to the first and summarize interval changes."
                    )
                    llm_response = await llm_service.generate_with_images(
                        prompt=prompt_text,
                        images_bytes=[baseline_bytes, follow_up_bytes],
                        system_prompt=system_prompt,
                        max_new_tokens=260,
                        min_new_tokens=80,
                        do_sample=False,
                        repetition_penalty=1.1,
                    )
                    cxr_note = (
                        "Auto CXR comparison "
                        f"(baseline {baseline_date} -> follow-up {follow_up_date}): "
                        f"{llm_response.text}"
                    )
            except Exception as exc:
                logger.warning(
                    "Auto CXR comparison failed for document %s: %s",
                    document.id,
                    exc,
                    exc_info=True,
                )
                cxr_note = (
                    f"Auto CXR comparison unavailable: {type(exc).__name__}: {str(exc)}"
                )

            _append_document_note(document, cxr_note)
            await db.flush()

        try:
            processor = DocumentProcessor(db)
            await processor.process_document(
                document_id=document.id,
                create_memory_chunks=True,
            )
            await db.refresh(document)
        except Exception as exc:  # noqa: BLE001 - do not fail upload on processing errors
            logger.warning(
                "Auto-processing failed for document %s: %s",
                document.id,
                exc,
            )

        return DocumentResponse.model_validate(document)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await clear_cache(f"documents:{current_user.id}:")


@router.post("/{document_id}/process", response_model=DocumentProcessResponse)
async def process_document(
    document_id: int,
    request: DocumentProcessRequest = DocumentProcessRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Process a document: extract text and create memory chunks."""
    await _get_document_for_user(
        document_id=document_id, db=db, current_user=current_user
    )
    processor = DocumentProcessor(db)

    try:
        document = await processor.process_document(
            document_id=document_id,
            create_memory_chunks=request.create_memory_chunks,
        )
        result = await db.execute(
            select(MemoryChunk).where(MemoryChunk.document_id == document_id)
        )
        chunks = result.scalars().all()

        return DocumentProcessResponse(
            document_id=document.id,
            status=document.processing_status,
            page_count=document.page_count,
            chunks_created=len(chunks),
            text_preview=document.extracted_text[:500]
            if document.extracted_text
            else None,
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
    """Process all pending documents."""
    processor = DocumentProcessor(db)
    result = await db.execute(
        select(Document)
        .join(Patient, Document.patient_id == Patient.id)
        .where(
            Document.processing_status == "pending", Patient.user_id == current_user.id
        )
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


@router.get("/health/ocr", response_model=dict)
async def check_ocr_availability() -> dict:
    """Check if OCR (Tesseract) is available on the backend."""
    from app.services.documents.extraction import ImageExtractor

    extractor = ImageExtractor()
    available = extractor._tesseract_available  # noqa: SLF001 - simple feature flag
    return {
        "available": available,
        "message": (
            "OCR is available"
            if available
            else (
                "Tesseract OCR is not installed or not working. "
                "Image/scanned PDF processing will return empty text. "
                "Install Tesseract (for example, 'brew install tesseract' on macOS)."
            )
        ),
    }


@router.post("/{document_id}/reprocess", response_model=DocumentProcessResponse)
async def reprocess_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Reprocess a document (delete existing chunks and extract again)."""
    await _get_document_for_user(
        document_id=document_id, db=db, current_user=current_user
    )
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
            text_preview=document.extracted_text[:500]
            if document.extracted_text
            else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        await clear_cache(f"documents:{current_user.id}:")


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    patient_id: int | None = None,
    document_type: str | None = None,
    processed_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List documents with optional filtering."""
    cache_key = CacheKeys.documents(
        current_user.id, patient_id, document_type, processed_only, skip, limit
    )
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
        await get_patient_for_user(
            patient_id=patient_id, db=db, current_user=current_user
        )
        query = query.where(Document.patient_id == patient_id)

    if document_type:
        query = query.where(Document.document_type == document_type)

    if processed_only:
        query = query.where(Document.is_processed)

    query = query.order_by(Document.received_date.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    documents = result.scalars().all()

    response = [DocumentResponse.model_validate(doc) for doc in documents]
    await set_cached(
        cache_key, response, ttl_seconds=settings.response_cache_ttl_seconds
    )
    return response


@router.get("/{document_id}/status", response_model=dict)
async def get_document_status(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> dict:
    """Get detailed processing and indexing status for a document."""
    document = await _get_document_for_user(
        document_id=document_id,
        db=db,
        current_user=current_user,
    )

    result = await db.execute(
        select(
            func.count(MemoryChunk.id).label("total"),
            func.sum(cast(MemoryChunk.is_indexed, Integer)).label("indexed"),
        ).where(MemoryChunk.document_id == document_id)
    )
    stats = result.first()
    total_chunks = int(stats.total or 0)
    indexed_chunks = int(stats.indexed or 0)

    return {
        "document_id": document.id,
        "patient_id": document.patient_id,
        "processing_status": document.processing_status,
        "is_processed": document.is_processed,
        "processed_at": document.processed_at,
        "processing_error": document.processing_error,
        "extracted_text_length": len(document.extracted_text)
        if document.extracted_text
        else 0,
        "extracted_text_preview": (
            document.extracted_text[:200] if document.extracted_text else None
        ),
        "chunks": {
            "total": total_chunks,
            "indexed": indexed_chunks,
            "not_indexed": max(total_chunks - indexed_chunks, 0),
        },
        "ocr_confidence": document.ocr_confidence,
        "ocr_language": document.ocr_language,
        "page_count": document.page_count,
    }


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get document details including extracted text."""
    document = await _get_document_for_user(
        document_id=document_id, db=db, current_user=current_user
    )

    return DocumentDetail.model_validate(document)


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Download the original document file."""
    document = await _get_document_for_user(
        document_id=document_id, db=db, current_user=current_user
    )

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
    document = await _get_document_for_user(
        document_id=document_id, db=db, current_user=current_user
    )

    if not document.is_processed:
        raise HTTPException(
            status_code=400,
            detail="Document has not been processed. Call /process endpoint first.",
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
    document = await _get_document_for_user(
        document_id=document_id, db=db, current_user=current_user
    )

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


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete a document and its associated file and memory chunks."""
    service = DocumentUploadService(db)
    document = await _get_document_for_user(
        document_id=document_id, db=db, current_user=current_user
    )
    await db.execute(
        MemoryChunk.__table__.delete().where(MemoryChunk.document_id == document.id)
    )
    deleted = await service.delete_document(document_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    await clear_cache(f"documents:{current_user.id}:")


@router.get("/patient/{patient_id}", response_model=list[DocumentResponse])
async def get_patient_documents(
    patient_id: int,
    document_type: str | None = None,
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
