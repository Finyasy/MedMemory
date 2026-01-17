"""Pydantic schemas for Memory API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================
# Search Schemas
# ============================================

class SearchRequest(BaseModel):
    """Request schema for semantic search."""
    
    query: str = Field(..., min_length=1, max_length=1000)
    patient_id: Optional[int] = None
    source_types: Optional[list[str]] = Field(
        None,
        description="Filter by source types: lab_result, medication, encounter, document"
    )
    limit: int = Field(10, ge=1, le=100)
    min_similarity: float = Field(0.3, ge=0.0, le=1.0)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class SearchResultItem(BaseModel):
    """A single search result."""
    
    chunk_id: int
    patient_id: int
    content: str
    source_type: str
    source_id: Optional[int] = None
    similarity_score: float
    context_date: Optional[datetime] = None
    chunk_type: Optional[str] = None


class SearchResponse(BaseModel):
    """Response schema for semantic search."""
    
    query: str
    results: list[SearchResultItem]
    total_results: int
    search_time_ms: float


# ============================================
# Indexing Schemas
# ============================================

class IndexTextRequest(BaseModel):
    """Request to index custom text into memory."""
    
    patient_id: int
    content: str = Field(..., min_length=1)
    source_type: str = Field("custom", max_length=50)
    context_date: Optional[datetime] = None
    chunk_type: Optional[str] = Field(None, max_length=50)
    importance_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class IndexPatientRequest(BaseModel):
    """Request to index all records for a patient."""
    
    patient_id: int


class IndexingStatsResponse(BaseModel):
    """Response with indexing statistics."""
    
    lab_results: int = 0
    medications: int = 0
    encounters: int = 0
    documents: int = 0
    total_chunks: int = 0


# ============================================
# Memory Chunk Schemas
# ============================================

class MemoryChunkResponse(BaseModel):
    """Response schema for a memory chunk."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    patient_id: int
    content: str
    source_type: str
    source_id: Optional[int] = None
    source_table: Optional[str] = None
    chunk_index: int = 0
    page_number: Optional[int] = None
    context_date: Optional[datetime] = None
    chunk_type: Optional[str] = None
    importance_score: Optional[float] = None
    is_indexed: bool
    indexed_at: Optional[datetime] = None
    created_at: datetime


class MemoryStatsResponse(BaseModel):
    """Statistics about indexed memory."""
    
    total: int = 0
    by_source_type: dict[str, int] = {}
    patient_id: Optional[int] = None


# ============================================
# Context Retrieval Schemas
# ============================================

class ContextRequest(BaseModel):
    """Request to get context for a question."""
    
    patient_id: int
    question: str = Field(..., min_length=1, max_length=1000)
    max_chunks: int = Field(10, ge=1, le=50)
    max_tokens: int = Field(2000, ge=100, le=8000)


class ContextResponse(BaseModel):
    """Response with retrieved context."""
    
    patient_id: int
    question: str
    context: str
    num_chunks: int
    context_length: int


# ============================================
# Similar Chunks Schemas
# ============================================

class SimilarChunksRequest(BaseModel):
    """Request to find similar chunks."""
    
    chunk_id: int
    limit: int = Field(5, ge=1, le=20)
    same_patient_only: bool = True


class SimilarChunksResponse(BaseModel):
    """Response with similar chunks."""
    
    source_chunk_id: int
    similar_chunks: list[SearchResultItem]
