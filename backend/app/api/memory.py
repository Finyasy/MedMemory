"""Memory and search API endpoints.

Provides semantic search over the medical memory and
endpoints for managing the vector index.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import MemoryChunk, Patient
from app.schemas.memory import (
    ContextRequest,
    ContextResponse,
    IndexingStatsResponse,
    IndexPatientRequest,
    IndexTextRequest,
    MemoryChunkResponse,
    MemoryStatsResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SimilarChunksRequest,
    SimilarChunksResponse,
)
from app.services.embeddings import (
    EmbeddingService,
    MemoryIndexingService,
    SimilaritySearchService,
)

router = APIRouter(prefix="/memory", tags=["Memory & Search"])


# ============================================
# Semantic Search
# ============================================

@router.post("/search", response_model=SearchResponse)
async def semantic_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Perform semantic search over the medical memory.
    
    Finds relevant medical information based on natural language queries.
    Uses vector similarity to match queries against indexed medical records.
    
    Examples:
    - "What are the patient's current medications?"
    - "Any abnormal lab results in the past year?"
    - "History of cardiac conditions"
    """
    search_service = SimilaritySearchService(db)
    
    response = await search_service.search(
        query=request.query,
        patient_id=request.patient_id,
        source_types=request.source_types,
        limit=request.limit,
        min_similarity=request.min_similarity,
        date_from=request.date_from,
        date_to=request.date_to,
    )
    
    return SearchResponse(
        query=response.query,
        results=[
            SearchResultItem(
                chunk_id=r.chunk_id,
                patient_id=r.patient_id,
                content=r.content,
                source_type=r.source_type,
                source_id=r.source_id,
                similarity_score=r.similarity_score,
                context_date=r.context_date,
                chunk_type=r.chunk_type,
            )
            for r in response.results
        ],
        total_results=response.total_results,
        search_time_ms=response.search_time_ms,
    )


@router.get("/search/patient/{patient_id}", response_model=SearchResponse)
async def search_patient_history(
    patient_id: int,
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    min_similarity: float = Query(0.3, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """Search within a specific patient's medical history.
    
    Convenient endpoint for patient-specific searches.
    """
    # Verify patient exists
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patient not found")
    
    search_service = SimilaritySearchService(db)
    response = await search_service.search_patient_history(
        patient_id=patient_id,
        query=query,
        limit=limit,
        min_similarity=min_similarity,
    )
    
    return SearchResponse(
        query=response.query,
        results=[
            SearchResultItem(
                chunk_id=r.chunk_id,
                patient_id=r.patient_id,
                content=r.content,
                source_type=r.source_type,
                source_id=r.source_id,
                similarity_score=r.similarity_score,
                context_date=r.context_date,
                chunk_type=r.chunk_type,
            )
            for r in response.results
        ],
        total_results=response.total_results,
        search_time_ms=response.search_time_ms,
    )


# ============================================
# Context Retrieval (for LLM)
# ============================================

@router.post("/context", response_model=ContextResponse)
async def get_context_for_question(
    request: ContextRequest,
    db: AsyncSession = Depends(get_db),
):
    """Get relevant context for answering a question.
    
    Returns concatenated relevant chunks optimized for feeding into an LLM.
    Useful for RAG (Retrieval-Augmented Generation) workflows.
    """
    search_service = SimilaritySearchService(db)
    
    context = await search_service.get_patient_context(
        patient_id=request.patient_id,
        query=request.question,
        max_chunks=request.max_chunks,
        max_tokens=request.max_tokens,
    )
    
    # Count chunks in context
    num_chunks = context.count("---") + 1 if context else 0
    
    return ContextResponse(
        patient_id=request.patient_id,
        question=request.question,
        context=context,
        num_chunks=num_chunks,
        context_length=len(context),
    )


# ============================================
# Similar Chunks
# ============================================

@router.post("/similar", response_model=SimilarChunksResponse)
async def find_similar_chunks(
    request: SimilarChunksRequest,
    db: AsyncSession = Depends(get_db),
):
    """Find chunks similar to a given chunk.
    
    Useful for finding related information or expanding context.
    """
    search_service = SimilaritySearchService(db)
    
    similar = await search_service.find_similar_chunks(
        chunk_id=request.chunk_id,
        limit=request.limit,
        same_patient_only=request.same_patient_only,
    )
    
    return SimilarChunksResponse(
        source_chunk_id=request.chunk_id,
        similar_chunks=[
            SearchResultItem(
                chunk_id=r.chunk_id,
                patient_id=r.patient_id,
                content=r.content,
                source_type=r.source_type,
                source_id=r.source_id,
                similarity_score=r.similarity_score,
                context_date=r.context_date,
                chunk_type=r.chunk_type,
            )
            for r in similar
        ],
    )


# ============================================
# Indexing
# ============================================

@router.post("/index/text", response_model=IndexingStatsResponse)
async def index_custom_text(
    request: IndexTextRequest,
    db: AsyncSession = Depends(get_db),
):
    """Index custom text content into memory.
    
    Useful for adding notes, summaries, or other text that
    isn't part of standard medical records.
    """
    indexing_service = MemoryIndexingService(db)
    
    chunks = await indexing_service.index_text(
        patient_id=request.patient_id,
        content=request.content,
        source_type=request.source_type,
        context_date=request.context_date,
        chunk_type=request.chunk_type,
        importance_score=request.importance_score,
    )
    
    return IndexingStatsResponse(total_chunks=len(chunks))


@router.post("/index/patient/{patient_id}", response_model=IndexingStatsResponse)
async def index_patient_records(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Index all records for a patient.
    
    This indexes:
    - Lab results
    - Medications
    - Encounters
    - Processed documents
    
    Run this after ingesting patient data to enable semantic search.
    """
    # Verify patient exists
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patient not found")
    
    indexing_service = MemoryIndexingService(db)
    stats = await indexing_service.index_all_for_patient(patient_id)
    
    return IndexingStatsResponse(**stats)


@router.post("/reindex/chunk/{chunk_id}", response_model=MemoryChunkResponse)
async def reindex_chunk(
    chunk_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Re-generate embedding for a specific chunk."""
    indexing_service = MemoryIndexingService(db)
    
    try:
        chunk = await indexing_service.reindex_chunk(chunk_id)
        return MemoryChunkResponse.model_validate(chunk)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================
# Memory Management
# ============================================

@router.get("/chunks", response_model=list[MemoryChunkResponse])
async def list_memory_chunks(
    patient_id: Optional[int] = None,
    source_type: Optional[str] = None,
    indexed_only: bool = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List memory chunks with optional filtering."""
    query = select(MemoryChunk)
    
    if patient_id:
        query = query.where(MemoryChunk.patient_id == patient_id)
    
    if source_type:
        query = query.where(MemoryChunk.source_type == source_type)
    
    if indexed_only:
        query = query.where(MemoryChunk.is_indexed == True)
    
    query = query.order_by(MemoryChunk.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    chunks = result.scalars().all()
    
    return [MemoryChunkResponse.model_validate(c) for c in chunks]


@router.get("/chunks/{chunk_id}", response_model=MemoryChunkResponse)
async def get_memory_chunk(
    chunk_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific memory chunk."""
    result = await db.execute(
        select(MemoryChunk).where(MemoryChunk.id == chunk_id)
    )
    chunk = result.scalar_one_or_none()
    
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    
    return MemoryChunkResponse.model_validate(chunk)


@router.delete("/chunks/{chunk_id}", status_code=204)
async def delete_memory_chunk(
    chunk_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific memory chunk."""
    result = await db.execute(
        select(MemoryChunk).where(MemoryChunk.id == chunk_id)
    )
    chunk = result.scalar_one_or_none()
    
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    
    await db.delete(chunk)


@router.delete("/patient/{patient_id}/memory", status_code=200)
async def delete_patient_memory(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete all memory chunks for a patient.
    
    Warning: This is irreversible. You'll need to re-index the patient's data.
    """
    indexing_service = MemoryIndexingService(db)
    count = await indexing_service.delete_patient_memory(patient_id)
    
    return {"deleted_chunks": count}


# ============================================
# Statistics
# ============================================

@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_stats(
    patient_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get statistics about indexed memory."""
    search_service = SimilaritySearchService(db)
    counts = await search_service.count_indexed_chunks(patient_id)
    
    total = counts.pop("total", 0)
    
    return MemoryStatsResponse(
        total=total,
        by_source_type=counts,
        patient_id=patient_id,
    )


# ============================================
# Embedding Info
# ============================================

@router.get("/embedding/info")
async def get_embedding_info():
    """Get information about the embedding model."""
    embedding_service = EmbeddingService.get_instance()
    
    return {
        "model_name": embedding_service.model_name,
        "dimension": embedding_service.dimension,
        "device": embedding_service.device,
    }
