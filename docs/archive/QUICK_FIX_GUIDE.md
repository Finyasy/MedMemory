# Quick Fix Guide: "No Relevant Information Found"

## Immediate Actions (Do These First)

### 1. Auto-Process Documents After Upload ⚡

**Problem**: Documents uploaded but never processed → no chunks exist

**Fix**: Add automatic processing to upload endpoint

**File**: `backend/app/api/documents.py`

**Change** (around line 93):
```python
# After document creation, add:
from app.services.documents.processor import DocumentProcessor

# ... existing upload code ...
document = await service.upload_document(...)

# ADD THIS: Auto-process the document
if document:
    try:
        processor = DocumentProcessor(db)
        await processor.process_document(
            document_id=document.id,
            create_memory_chunks=True
        )
        # Refresh to get updated status
        await db.refresh(document)
    except Exception as e:
        # Log but don't fail upload
        logger.warning(f"Auto-processing failed for document {document.id}: {e}")
```

---

### 2. Make Indexing Failures Visible 🔍

**Problem**: Indexing fails silently, chunks exist but `is_indexed=False`

**Fix**: Store indexing errors and make them visible

**File**: `backend/app/services/documents/processor.py`

**Change** (around line 150):
```python
# Replace the try/except block (lines 150-155) with:
try:
    indexing_service = MemoryIndexingService(self.db)
    indexed_chunks = await indexing_service.index_document_chunks(document)
    self.logger.info(
        "Indexed %d chunks for document %s",
        len(indexed_chunks),
        document_id
    )
except Exception as idx_err:
    # Store error in document record
    error_msg = f"Indexing failed: {str(idx_err)}"
    self.logger.error(error_msg, exc_info=True)
    
    # Update document with indexing error
    document.processing_error = error_msg
    await self.db.flush()
    
    # Re-raise if critical, or just log if non-critical
    # For now, log but continue
    self.logger.warning(
        "Document %s processed but indexing failed. "
        "Chunks exist but are not searchable.",
        document_id
    )
```

---

### 3. Add OCR Availability Check 🖼️

**Problem**: Missing Tesseract causes silent OCR failures

**Fix**: Check OCR availability and warn users

**File**: `backend/app/api/documents.py`

**Add new endpoint** (after existing endpoints):
```python
@router.get("/health/ocr", response_model=dict)
async def check_ocr_availability():
    """Check if OCR (Tesseract) is available."""
    from app.services.documents.extraction import ImageExtractor
    extractor = ImageExtractor()
    return {
        "available": extractor._tesseract_available,
        "message": (
            "OCR is available" if extractor._tesseract_available
            else "Tesseract OCR is not installed. Image/scanned PDF processing will fail."
        )
    }
```

**File**: `backend/app/services/documents/extraction.py`

**Change** (around line 299):
```python
# In extract_from_bytes_sync, replace lines 299-304 with:
if self._tesseract_available:
    text, confidence = self._ocr_with_tesseract_sync(image)
else:
    # Log warning instead of silently failing
    import logging
    logger = logging.getLogger("medmemory")
    logger.warning(
        "Tesseract OCR not available. Cannot extract text from image. "
        "Install Tesseract: brew install tesseract (macOS) or apt-get install tesseract-ocr (Linux)"
    )
    text = ""
    confidence = 0.0
```

---

### 4. Add Diagnostic Endpoint 📊

**Problem**: No way to check document processing/indexing status

**Fix**: Add status endpoint

**File**: `backend/app/api/documents.py`

**Add new endpoint**:
```python
@router.get("/{document_id}/status", response_model=dict)
async def get_document_status(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get detailed processing and indexing status for a document."""
    from sqlalchemy import select, func
    from app.models import MemoryChunk
    
    # Verify access
    document = await _get_document_for_user(
        document_id=document_id,
        db=db,
        current_user=current_user
    )
    
    # Count chunks
    result = await db.execute(
        select(
            func.count(MemoryChunk.id).label("total"),
            func.sum(func.cast(MemoryChunk.is_indexed, int)).label("indexed")
        ).where(MemoryChunk.document_id == document_id)
    )
    stats = result.first()
    
    return {
        "document_id": document_id,
        "processing_status": document.processing_status,
        "is_processed": document.is_processed,
        "processing_error": document.processing_error,
        "extracted_text_length": len(document.extracted_text) if document.extracted_text else 0,
        "extracted_text_preview": (
            document.extracted_text[:200] if document.extracted_text
            else None
        ),
        "chunks": {
            "total": stats.total or 0,
            "indexed": stats.indexed or 0,
            "not_indexed": (stats.total or 0) - (stats.indexed or 0),
        },
        "ocr_confidence": document.ocr_confidence,
        "page_count": document.page_count,
    }
```

---

### 5. Improve RAG Error Messages 💬

**Problem**: Generic "No relevant information" doesn't help users

**Fix**: Return specific, actionable error messages

**File**: `backend/app/services/llm/rag.py`

**Change** (around line 152):
```python
# Replace the generic message with diagnostic info
if not context_result.synthesized_context.total_chunks_used:
    # Check why no chunks were found
    from sqlalchemy import select, func
    from app.models import MemoryChunk
    
    result = await self.db.execute(
        select(func.count(MemoryChunk.id)).where(
            MemoryChunk.patient_id == patient_id
        )
    )
    total_chunks = result.scalar() or 0
    
    result = await self.db.execute(
        select(func.count(MemoryChunk.id)).where(
            MemoryChunk.patient_id == patient_id,
            MemoryChunk.is_indexed == True
        )
    )
    indexed_chunks = result.scalar() or 0
    
    # Build helpful error message
    if total_chunks == 0:
        answer = (
            "No documents have been processed for this patient. "
            "Please upload and process documents first."
        )
    elif indexed_chunks == 0:
        answer = (
            f"Found {total_chunks} document chunks, but they are not indexed for search. "
            "This usually means embedding generation failed. "
            "Please reprocess the documents or contact support."
        )
    else:
        answer = (
            f"No relevant information found for this query. "
            f"The patient has {indexed_chunks} indexed chunks, but none matched your question. "
            "Try rephrasing your question or check if the relevant documents have been processed."
        )
    
    # ... rest of the code ...
```

---

## Testing Checklist

After implementing fixes, test:

- [ ] Upload a PDF → verify it auto-processes
- [ ] Upload an image without Tesseract → verify warning appears
- [ ] Check `/api/v1/documents/{id}/status` → verify status is accurate
- [ ] Upload document → wait for processing → try "Summarize in chat"
- [ ] Check logs for indexing errors
- [ ] Verify chunks are created with `is_indexed=True`

---

## Quick Verification Commands

```bash
# Check if Tesseract is installed
python -c "import pytesseract; print(pytesseract.get_tesseract_version())"

# Check document status (replace DOC_ID and TOKEN)
curl -H "Authorization: Bearer <TOKEN>" \
  http://localhost:8000/api/v1/documents/<DOC_ID>/status

# Check OCR availability
curl http://localhost:8000/api/v1/documents/health/ocr

# Check memory stats for patient
curl -H "Authorization: Bearer <TOKEN>" \
  "http://localhost:8000/api/v1/memory/stats?patient_id=<PATIENT_ID>"
```

---

## Priority Order

1. **Auto-processing** (Fix 1) - Fixes 80% of cases
2. **Indexing visibility** (Fix 2) - Makes failures visible
3. **Better error messages** (Fix 5) - Improves UX immediately
4. **OCR check** (Fix 3) - Prevents future issues
5. **Diagnostic endpoint** (Fix 4) - Enables troubleshooting

---

## Estimated Time

- Fix 1: 1-2 hours
- Fix 2: 30 minutes
- Fix 3: 1 hour
- Fix 4: 1 hour
- Fix 5: 30 minutes

**Total**: ~4-5 hours for all fixes
