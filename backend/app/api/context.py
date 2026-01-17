"""Context Engine API endpoints.

Provides intelligent context retrieval for medical Q&A.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_patient_for_user
from app.database import get_db
from app.models import User
from app.schemas.context import (
    ContextRequest,
    ContextResponse,
    ContextSectionSchema,
    QueryAnalysisResponse,
    QuickSearchRequest,
    QuickSearchResponse,
    QuickSearchResult,
    RankedResultItem,
    RetrievalStatsResponse,
    SimpleContextRequest,
    SimpleContextResponse,
    SynthesizedContextResponse,
    TemporalContextSchema,
)
from app.services.context import ContextEngine

router = APIRouter(prefix="/context", tags=["Context Engine"])


# ============================================
# Main Context Retrieval
# ============================================

@router.post("/", response_model=ContextResponse)
async def get_context(
    request: ContextRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get optimized context for answering a medical question.
    
    This is the main entry point for the context engine. It:
    1. Analyzes the query to understand intent
    2. Retrieves relevant content using hybrid search
    3. Ranks and filters results
    4. Synthesizes context for LLM consumption
    
    The response includes detailed information about each step
    for transparency and debugging.
    """
    # Verify patient exists
    await get_patient_for_user(
        patient_id=request.patient_id,
        db=db,
        current_user=current_user,
    )
    
    # Run context engine
    engine = ContextEngine(db)
    engine_result = await engine.get_context(
        query=request.query,
        patient_id=request.patient_id,
        max_results=request.max_results,
        max_tokens=request.max_tokens,
        min_score=request.min_score,
        system_prompt=request.system_prompt,
    )
    
    # Build response
    qa = engine_result.query_analysis
    
    return ContextResponse(
        query_analysis=QueryAnalysisResponse(
            original_query=qa.original_query,
            normalized_query=qa.normalized_query,
            intent=qa.intent.value,
            confidence=qa.confidence,
            medical_entities=qa.medical_entities,
            medication_names=qa.medication_names,
            test_names=qa.test_names,
            condition_names=qa.condition_names,
            temporal=TemporalContextSchema(
                is_temporal=qa.temporal.is_temporal,
                time_range=qa.temporal.time_range,
                date_from=qa.temporal.date_from,
                date_to=qa.temporal.date_to,
                relative_days=qa.temporal.relative_days,
            ),
            data_sources=[s.value for s in qa.data_sources],
            keywords=qa.keywords,
            use_semantic_search=qa.use_semantic_search,
            use_keyword_search=qa.use_keyword_search,
            boost_recent=qa.boost_recent,
        ),
        retrieval_stats=RetrievalStatsResponse(
            total_semantic=engine_result.retrieval_response.total_semantic,
            total_keyword=engine_result.retrieval_response.total_keyword,
            total_combined=engine_result.retrieval_response.total_combined,
            retrieval_time_ms=engine_result.retrieval_response.retrieval_time_ms,
        ),
        ranked_results=[
            RankedResultItem(
                id=r.result.id,
                content=r.result.content[:500] + "..." if len(r.result.content) > 500 else r.result.content,
                source_type=r.result.source_type,
                source_id=r.result.source_id,
                context_date=r.result.context_date,
                final_score=r.final_score,
                relevance_score=r.relevance_score,
                diversity_penalty=r.diversity_penalty,
                reasoning=r.reasoning,
            )
            for r in engine_result.ranked_results[:10]  # Limit for response size
        ],
        synthesized_context=SynthesizedContextResponse(
            query=engine_result.synthesized_context.query,
            sections=[
                ContextSectionSchema(
                    title=s.title,
                    content=s.content[:1000] + "..." if len(s.content) > 1000 else s.content,
                    source_type=s.source_type,
                    relevance=s.relevance,
                    date=s.date,
                )
                for s in engine_result.synthesized_context.sections
            ],
            full_context=engine_result.synthesized_context.full_context,
            total_chunks_used=engine_result.synthesized_context.total_chunks_used,
            total_characters=engine_result.synthesized_context.total_characters,
            estimated_tokens=engine_result.synthesized_context.estimated_tokens,
            source_types_included=engine_result.synthesized_context.source_types_included,
            earliest_date=engine_result.synthesized_context.earliest_date,
            latest_date=engine_result.synthesized_context.latest_date,
        ),
        prompt=engine_result.prompt,
        analysis_time_ms=engine_result.analysis_time_ms,
        retrieval_time_ms=engine_result.retrieval_time_ms,
        ranking_time_ms=engine_result.ranking_time_ms,
        synthesis_time_ms=engine_result.synthesis_time_ms,
        total_time_ms=engine_result.total_time_ms,
    )


@router.post("/simple", response_model=SimpleContextResponse)
async def get_simple_context(
    request: SimpleContextRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get simplified context for LLM consumption.
    
    A simpler endpoint that returns just the essentials:
    - The synthesized context
    - The complete prompt
    - Basic metadata
    
    Use this for direct LLM integration.
    """
    # Verify patient exists
    await get_patient_for_user(
        patient_id=request.patient_id,
        db=db,
        current_user=current_user,
    )
    
    engine = ContextEngine(db)
    engine_result = await engine.get_context(
        query=request.query,
        patient_id=request.patient_id,
        max_tokens=request.max_tokens,
    )
    
    return SimpleContextResponse(
        query=request.query,
        patient_id=request.patient_id,
        context=engine_result.synthesized_context.full_context,
        prompt=engine_result.prompt,
        num_sources=engine_result.synthesized_context.total_chunks_used,
        estimated_tokens=engine_result.synthesized_context.estimated_tokens,
        processing_time_ms=engine_result.total_time_ms,
    )


# ============================================
# Query Analysis
# ============================================

@router.post("/analyze", response_model=QueryAnalysisResponse)
async def analyze_query(
    query: str = Query(..., min_length=1, max_length=2000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Analyze a query without retrieval.
    
    Useful for understanding how the context engine interprets queries.
    """
    engine = ContextEngine(db)
    qa = await engine.analyze_query(query)
    
    return QueryAnalysisResponse(
        original_query=qa.original_query,
        normalized_query=qa.normalized_query,
        intent=qa.intent.value,
        confidence=qa.confidence,
        medical_entities=qa.medical_entities,
        medication_names=qa.medication_names,
        test_names=qa.test_names,
        condition_names=qa.condition_names,
        temporal=TemporalContextSchema(
            is_temporal=qa.temporal.is_temporal,
            time_range=qa.temporal.time_range,
            date_from=qa.temporal.date_from,
            date_to=qa.temporal.date_to,
            relative_days=qa.temporal.relative_days,
        ),
        data_sources=[s.value for s in qa.data_sources],
        keywords=qa.keywords,
        use_semantic_search=qa.use_semantic_search,
        use_keyword_search=qa.use_keyword_search,
        boost_recent=qa.boost_recent,
    )


# ============================================
# Quick Search
# ============================================

@router.post("/search", response_model=QuickSearchResponse)
async def quick_search(
    request: QuickSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Quick hybrid search without full context synthesis.
    
    Faster than full context retrieval. Returns ranked results
    without building the complete LLM prompt.
    """
    import time
    start = time.time()
    
    # Verify patient exists
    result = await db.execute(
        select(Patient).where(Patient.id == request.patient_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patient not found")
    
    engine = ContextEngine(db)
    results = await engine.search(
        query=request.query,
        patient_id=request.patient_id,
        limit=request.limit,
        source_types=request.source_types,
    )
    
    search_time = (time.time() - start) * 1000
    
    return QuickSearchResponse(
        query=request.query,
        results=[
            QuickSearchResult(
                id=r["id"],
                content=r["content"][:500] + "..." if len(r["content"]) > 500 else r["content"],
                source_type=r["source_type"],
                source_id=r["source_id"],
                score=r["score"],
                date=r["date"],
            )
            for r in results
        ],
        total_results=len(results),
        search_time_ms=search_time,
    )


# ============================================
# Prompt Generation
# ============================================

@router.get("/prompt/patient/{patient_id}")
async def generate_prompt(
    patient_id: int,
    question: str = Query(..., min_length=1, max_length=2000),
    max_tokens: int = Query(4000, ge=500, le=8000),
    system_prompt: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Generate an LLM-ready prompt for a patient question.
    
    Returns just the prompt string, ready to send to an LLM.
    """
    # Verify patient exists
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patient not found")
    
    engine = ContextEngine(db, max_tokens=max_tokens)
    engine_result = await engine.get_context(
        query=question,
        patient_id=patient_id,
        system_prompt=system_prompt,
    )
    
    return {
        "prompt": engine_result.prompt,
        "estimated_tokens": engine_result.synthesized_context.estimated_tokens,
        "sources_used": engine_result.synthesized_context.total_chunks_used,
    }
