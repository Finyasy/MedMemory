"""Context Engine - The main orchestrator for intelligent retrieval.

Combines all components:
- Query Analyzer: Understand user intent
- Hybrid Retriever: Get relevant content
- Context Ranker: Re-rank for quality
- Context Synthesizer: Build LLM-ready context
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.context.analyzer import QueryAnalyzer, QueryAnalysis
from app.services.context.ranker import ContextRanker, RankedResult
from app.services.context.retriever import HybridRetriever, RetrievalResponse
from app.services.context.synthesizer import ContextSynthesizer, SynthesizedContext
from app.services.embeddings import EmbeddingService


@dataclass
class ContextEngineResult:
    """Complete result from the context engine."""
    
    # Query analysis
    query_analysis: QueryAnalysis
    
    # Retrieval results
    retrieval_response: RetrievalResponse
    
    # Ranked results
    ranked_results: list[RankedResult]
    
    # Synthesized context
    synthesized_context: SynthesizedContext
    
    # LLM-ready prompt
    prompt: str
    
    # Timing
    analysis_time_ms: float = 0.0
    retrieval_time_ms: float = 0.0
    ranking_time_ms: float = 0.0
    synthesis_time_ms: float = 0.0
    total_time_ms: float = 0.0


class ContextEngine:
    """Main context engine that orchestrates intelligent retrieval.
    
    Usage:
        engine = ContextEngine(db)
        result = await engine.get_context(
            query="What medications is the patient currently taking?",
            patient_id=123,
        )
        
        # Use result.prompt for LLM
        # Or access individual components
    """
    
    def __init__(
        self,
        db: AsyncSession,
        embedding_service: Optional[EmbeddingService] = None,
        max_results: int = 15,
        max_tokens: int = 4000,
    ):
        """Initialize the context engine.
        
        Args:
            db: Database session
            embedding_service: Service for embeddings
            max_results: Maximum results to retrieve
            max_tokens: Maximum tokens in synthesized context
        """
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService.get_instance()
        self.max_results = max_results
        self.max_tokens = max_tokens
        
        # Initialize components
        self.analyzer = QueryAnalyzer()
        self.retriever = HybridRetriever(db, self.embedding_service)
        self.ranker = ContextRanker()
        self.synthesizer = ContextSynthesizer(max_tokens=max_tokens)
    
    async def get_context(
        self,
        query: str,
        patient_id: int,
        max_results: Optional[int] = None,
        max_tokens: Optional[int] = None,
        min_score: float = 0.3,
        system_prompt: Optional[str] = None,
    ) -> ContextEngineResult:
        """Get optimized context for answering a query.
        
        Args:
            query: Natural language query
            patient_id: Patient to query
            max_results: Override max results
            max_tokens: Override max tokens
            min_score: Minimum relevance score
            system_prompt: Custom system prompt for LLM
            
        Returns:
            ContextEngineResult with all components
        """
        import time
        total_start = time.time()
        
        # 1. Analyze query
        analysis_start = time.time()
        query_analysis = self.analyzer.analyze(query)
        analysis_time = (time.time() - analysis_start) * 1000
        
        # 2. Retrieve content
        retrieval_start = time.time()
        retrieval_response = await self.retriever.retrieve(
            query_analysis=query_analysis,
            patient_id=patient_id,
            limit=max_results or self.max_results,
            min_score=min_score,
        )
        retrieval_time = (time.time() - retrieval_start) * 1000
        
        # 3. Rank results
        ranking_start = time.time()
        ranked_results = self.ranker.rank(
            results=retrieval_response.results,
            query_analysis=query_analysis,
            max_results=max_results or self.max_results,
        )
        
        # Apply coverage re-ranking for summary/overview queries
        if query_analysis.intent.value in ["summary", "overview"]:
            ranked_results = self.ranker.rerank_for_coverage(
                ranked_results,
                min_per_source=2,
            )
        
        ranking_time = (time.time() - ranking_start) * 1000
        
        # 4. Synthesize context
        synthesis_start = time.time()
        synthesized_context = self.synthesizer.synthesize(
            ranked_results=ranked_results,
            query_analysis=query_analysis,
        )
        synthesis_time = (time.time() - synthesis_start) * 1000
        
        # 5. Build prompt
        prompt = self.synthesizer.create_prompt_context(
            synthesized=synthesized_context,
            system_prompt=system_prompt,
        )
        
        total_time = (time.time() - total_start) * 1000
        
        return ContextEngineResult(
            query_analysis=query_analysis,
            retrieval_response=retrieval_response,
            ranked_results=ranked_results,
            synthesized_context=synthesized_context,
            prompt=prompt,
            analysis_time_ms=analysis_time,
            retrieval_time_ms=retrieval_time,
            ranking_time_ms=ranking_time,
            synthesis_time_ms=synthesis_time,
            total_time_ms=total_time,
        )
    
    async def analyze_query(self, query: str) -> QueryAnalysis:
        """Analyze a query without retrieval (for debugging/testing).
        
        Args:
            query: Natural language query
            
        Returns:
            QueryAnalysis with extracted information
        """
        return self.analyzer.analyze(query)
    
    async def get_raw_retrieval(
        self,
        query: str,
        patient_id: int,
        limit: int = 20,
    ) -> RetrievalResponse:
        """Get raw retrieval results without ranking/synthesis.
        
        Useful for debugging or when you need direct access to retrieved content.
        """
        query_analysis = self.analyzer.analyze(query)
        return await self.retriever.retrieve(
            query_analysis=query_analysis,
            patient_id=patient_id,
            limit=limit,
        )
    
    async def search(
        self,
        query: str,
        patient_id: int,
        limit: int = 10,
        source_types: Optional[list[str]] = None,
    ) -> list[dict]:
        """Simple search interface returning dictionary results.
        
        Convenience method for basic search needs.
        """
        query_analysis = self.analyzer.analyze(query)
        
        # Override source types if provided
        if source_types:
            from app.services.context.analyzer import DataSource
            query_analysis.data_sources = [
                DataSource(s) for s in source_types
            ]
        
        retrieval_response = await self.retriever.retrieve(
            query_analysis=query_analysis,
            patient_id=patient_id,
            limit=limit,
        )
        
        return [
            {
                "id": r.id,
                "content": r.content,
                "source_type": r.source_type,
                "source_id": r.source_id,
                "score": r.combined_score,
                "date": r.context_date.isoformat() if r.context_date else None,
            }
            for r in retrieval_response.results
        ]
