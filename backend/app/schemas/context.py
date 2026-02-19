"""Pydantic schemas for Context Engine API."""

from datetime import datetime

from pydantic import BaseModel, Field


class TemporalContextSchema(BaseModel):
    """Temporal information from query."""

    is_temporal: bool = False
    time_range: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    relative_days: int | None = None


class QueryAnalysisResponse(BaseModel):
    """Response schema for query analysis."""

    original_query: str
    normalized_query: str
    intent: str
    confidence: float
    medical_entities: list[str] = []
    medication_names: list[str] = []
    test_names: list[str] = []
    condition_names: list[str] = []
    temporal: TemporalContextSchema
    data_sources: list[str] = []
    keywords: list[str] = []
    use_semantic_search: bool = True
    use_keyword_search: bool = False
    boost_recent: bool = False


class RetrievalResultItem(BaseModel):
    """A single retrieval result."""

    id: int
    content: str
    source_type: str
    source_id: int | None = None
    patient_id: int

    semantic_score: float = 0.0
    keyword_score: float = 0.0
    recency_score: float = 0.0
    combined_score: float = 0.0

    context_date: datetime | None = None
    chunk_index: int = 0


class RetrievalStatsResponse(BaseModel):
    """Statistics from retrieval."""

    total_semantic: int = 0
    total_keyword: int = 0
    total_combined: int = 0
    retrieval_time_ms: float = 0.0


# ============================================
# Ranked Results Schemas
# ============================================


class RankedResultItem(BaseModel):
    """A re-ranked result."""

    id: int
    content: str
    source_type: str
    source_id: int | None = None
    context_date: datetime | None = None

    final_score: float
    relevance_score: float
    diversity_penalty: float
    reasoning: str = ""


class ContextSectionSchema(BaseModel):
    """A section of context."""

    title: str
    content: str
    source_type: str
    relevance: float
    date: datetime | None = None


class SynthesizedContextResponse(BaseModel):
    """Synthesized context response."""

    query: str
    sections: list[ContextSectionSchema] = []
    full_context: str

    total_chunks_used: int = 0
    total_characters: int = 0
    estimated_tokens: int = 0
    source_types_included: list[str] = []

    earliest_date: datetime | None = None
    latest_date: datetime | None = None


class ContextRequest(BaseModel):
    """Request to get context for a question."""

    query: str = Field(..., min_length=1, max_length=2000)
    patient_id: int
    max_results: int | None = Field(15, ge=1, le=50)
    max_tokens: int | None = Field(4000, ge=500, le=8000)
    min_score: float = Field(0.3, ge=0.0, le=1.0)
    system_prompt: str | None = None


class ContextResponse(BaseModel):
    """Complete context engine response."""

    query_analysis: QueryAnalysisResponse
    retrieval_stats: RetrievalStatsResponse
    ranked_results: list[RankedResultItem]
    synthesized_context: SynthesizedContextResponse
    prompt: str
    analysis_time_ms: float
    retrieval_time_ms: float
    ranking_time_ms: float
    synthesis_time_ms: float
    total_time_ms: float


class SimpleContextRequest(BaseModel):
    """Simplified context request."""

    query: str = Field(..., min_length=1, max_length=2000)
    patient_id: int
    max_tokens: int = Field(4000, ge=500, le=8000)


class SimpleContextResponse(BaseModel):
    """Simplified context response with just the essentials."""

    query: str
    patient_id: int
    context: str
    prompt: str
    num_sources: int
    estimated_tokens: int
    processing_time_ms: float


class QuickSearchRequest(BaseModel):
    """Quick search request."""

    query: str = Field(..., min_length=1, max_length=1000)
    patient_id: int
    limit: int = Field(10, ge=1, le=50)
    source_types: list[str] | None = None


class QuickSearchResult(BaseModel):
    """Quick search result item."""

    id: int
    content: str
    source_type: str
    source_id: int | None = None
    score: float
    date: str | None = None


class QuickSearchResponse(BaseModel):
    """Quick search response."""

    query: str
    results: list[QuickSearchResult]
    total_results: int
    search_time_ms: float
