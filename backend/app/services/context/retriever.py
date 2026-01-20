"""Hybrid retriever combining vector and keyword search.

Implements multiple retrieval strategies:
- Semantic (vector) search for meaning-based matching
- Keyword search for exact term matching
- Filter-based retrieval for structured queries
- Temporal-aware retrieval for time-based queries
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import logging

from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Document,
    Encounter,
    LabResult,
    Medication,
    MemoryChunk,
)
from app.services.context.analyzer import DataSource, QueryAnalysis
from app.services.embeddings import EmbeddingService


@dataclass
class RetrievalResult:
    """A single retrieved result."""
    
    id: int
    content: str
    source_type: str
    source_id: Optional[int]
    patient_id: int
    
    # Scores
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    recency_score: float = 0.0
    combined_score: float = 0.0
    
    # Metadata
    context_date: Optional[datetime] = None
    chunk_index: int = 0
    page_number: Optional[int] = None
    
    def __hash__(self):
        return hash((self.id, self.source_type))
    
    def __eq__(self, other):
        if not isinstance(other, RetrievalResult):
            return False
        return self.id == other.id and self.source_type == other.source_type


@dataclass
class RetrievalResponse:
    """Response from hybrid retrieval."""
    
    results: list[RetrievalResult]
    total_semantic: int = 0
    total_keyword: int = 0
    total_combined: int = 0
    retrieval_time_ms: float = 0.0


class HybridRetriever:
    """Combines multiple retrieval strategies for optimal results.
    
    Retrieval strategies:
    1. Semantic search: Find conceptually similar content
    2. Keyword search: Find exact term matches
    3. Filter search: Query structured data directly
    4. Temporal boost: Prioritize recent content when relevant
    """
    
    def __init__(
        self,
        db: AsyncSession,
        embedding_service: Optional[EmbeddingService] = None,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.3,
        recency_weight: float = 0.1,
    ):
        """Initialize the hybrid retriever.
        
        Args:
            db: Database session
            embedding_service: Service for generating query embeddings
            semantic_weight: Weight for semantic search scores
            keyword_weight: Weight for keyword search scores
            recency_weight: Weight for recency scores
        """
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService.get_instance()
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.recency_weight = recency_weight
        self.logger = logging.getLogger("medmemory")
    
    async def retrieve(
        self,
        query_analysis: QueryAnalysis,
        patient_id: int,
        limit: int = 20,
        min_score: float = 0.3,
    ) -> RetrievalResponse:
        """Retrieve relevant content using hybrid search.
        
        Args:
            query_analysis: Analyzed query with intent and entities
            patient_id: Patient to search
            limit: Maximum results
            min_score: Minimum combined score threshold
            
        Returns:
            RetrievalResponse with ranked results
        """
        import time
        start_time = time.time()
        
        results: dict[tuple[int, str], RetrievalResult] = {}
        
        # Semantic search
        if query_analysis.use_semantic_search:
            try:
                semantic_results = await self._semantic_search(
                    query=query_analysis.normalized_query,
                    patient_id=patient_id,
                    source_types=[s.value for s in query_analysis.data_sources],
                    date_from=query_analysis.temporal.date_from,
                    date_to=query_analysis.temporal.date_to,
                    limit=limit * 2,  # Get more for fusion
                )
            except Exception:
                self.logger.exception("Semantic search failed; continuing with keyword-only search.")
                semantic_results = []
            
            for result in semantic_results:
                key = (result.id, result.source_type)
                if key not in results:
                    results[key] = result
                else:
                    results[key].semantic_score = max(
                        results[key].semantic_score,
                        result.semantic_score,
                    )
        
        # Keyword search
        if query_analysis.use_keyword_search and query_analysis.keywords:
            try:
                keyword_results = await self._keyword_search(
                    keywords=query_analysis.keywords,
                    patient_id=patient_id,
                    source_types=[s.value for s in query_analysis.data_sources],
                    date_from=query_analysis.temporal.date_from,
                    date_to=query_analysis.temporal.date_to,
                    limit=limit * 2,
                )
            except Exception:
                self.logger.exception("Keyword search failed; returning empty results.")
                keyword_results = []
            
            for result in keyword_results:
                key = (result.id, result.source_type)
                if key not in results:
                    results[key] = result
                else:
                    results[key].keyword_score = max(
                        results[key].keyword_score,
                        result.keyword_score,
                    )
        
        # Direct structured queries for specific intents
        if query_analysis.intent.value in ["list", "value", "status"]:
            structured_results = await self._structured_search(
                query_analysis=query_analysis,
                patient_id=patient_id,
                limit=limit,
            )
            
            for result in structured_results:
                key = (result.id, result.source_type)
                if key not in results:
                    results[key] = result
                else:
                    # Boost existing results
                    results[key].keyword_score += 0.2
        
        # Calculate combined scores
        all_results = list(results.values())
        
        for result in all_results:
            # Calculate recency score
            if query_analysis.boost_recent and result.context_date:
                days_ago = (datetime.now(timezone.utc) - result.context_date).days
                result.recency_score = max(0, 1 - (days_ago / 365))
            
            # Calculate combined score
            result.combined_score = (
                self.semantic_weight * result.semantic_score +
                self.keyword_weight * result.keyword_score +
                self.recency_weight * result.recency_score
            )
        
        # Filter and sort
        filtered_results = [r for r in all_results if r.combined_score >= min_score]
        sorted_results = sorted(
            filtered_results,
            key=lambda r: r.combined_score,
            reverse=True,
        )[:limit]
        
        retrieval_time = (time.time() - start_time) * 1000
        
        return RetrievalResponse(
            results=sorted_results,
            total_semantic=len([r for r in all_results if r.semantic_score > 0]),
            total_keyword=len([r for r in all_results if r.keyword_score > 0]),
            total_combined=len(sorted_results),
            retrieval_time_ms=retrieval_time,
        )
    
    async def _semantic_search(
        self,
        query: str,
        patient_id: int,
        source_types: list[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        limit: int,
    ) -> list[RetrievalResult]:
        """Perform semantic (vector) search."""
        # Generate query embedding
        query_embedding = await self.embedding_service.embed_query_async(query)
        
        # Build SQL query
        # Use CAST() instead of :: syntax for asyncpg compatibility
        sql = """
            SELECT 
                id,
                patient_id,
                content,
                source_type,
                source_id,
                context_date,
                chunk_index,
                page_number,
                1 - (embedding <=> CAST(:query_embedding AS vector)) as similarity
            FROM memory_chunks
            WHERE is_indexed = true
            AND patient_id = :patient_id
        """
        
        params = {
            "query_embedding": str(query_embedding),
            "patient_id": patient_id,
        }
        
        if source_types and "all" not in source_types:
            sql += " AND source_type = ANY(:source_types)"
            params["source_types"] = source_types
        
        if date_from:
            sql += " AND (context_date IS NULL OR context_date >= :date_from)"
            params["date_from"] = date_from
        
        if date_to:
            sql += " AND (context_date IS NULL OR context_date <= :date_to)"
            params["date_to"] = date_to
        
        sql += " ORDER BY similarity DESC LIMIT :limit"
        params["limit"] = limit
        
        result = await self.db.execute(text(sql), params)
        rows = result.fetchall()
        
        return [
            RetrievalResult(
                id=row.id,
                content=row.content,
                source_type=row.source_type,
                source_id=row.source_id,
                patient_id=row.patient_id,
                semantic_score=float(row.similarity),
                context_date=row.context_date,
                chunk_index=row.chunk_index,
                page_number=row.page_number,
            )
            for row in rows
        ]
    
    async def _keyword_search(
        self,
        keywords: list[str],
        patient_id: int,
        source_types: list[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        limit: int,
    ) -> list[RetrievalResult]:
        """Perform keyword-based search using PostgreSQL full-text search."""
        # Build keyword pattern
        keyword_pattern = "%|%".join(keywords)
        keyword_pattern = f"%{keyword_pattern}%"
        
        # Build SQL query
        sql = """
            SELECT 
                id,
                patient_id,
                content,
                source_type,
                source_id,
                context_date,
                chunk_index,
                page_number,
                (
                    SELECT COUNT(*)::float / :keyword_count
                    FROM unnest(CAST(:keywords AS text[])) AS kw
                    WHERE LOWER(content) LIKE '%' || LOWER(kw) || '%'
                ) as match_score
            FROM memory_chunks
            WHERE is_indexed = true
            AND patient_id = :patient_id
            AND (
        """
        
        # Add keyword conditions
        keyword_conditions = " OR ".join(
            [f"LOWER(content) LIKE '%' || LOWER(:kw{i}) || '%'" for i in range(len(keywords))]
        )
        sql += keyword_conditions + ")"
        
        params = {
            "patient_id": patient_id,
            "keywords": keywords,
            "keyword_count": len(keywords),
        }
        
        # Add keyword params
        for i, kw in enumerate(keywords):
            params[f"kw{i}"] = kw
        
        if source_types and "all" not in source_types:
            sql += " AND source_type = ANY(:source_types)"
            params["source_types"] = source_types
        
        if date_from:
            sql += " AND (context_date IS NULL OR context_date >= :date_from)"
            params["date_from"] = date_from
        
        if date_to:
            sql += " AND (context_date IS NULL OR context_date <= :date_to)"
            params["date_to"] = date_to
        
        sql += " ORDER BY match_score DESC LIMIT :limit"
        params["limit"] = limit
        
        result = await self.db.execute(text(sql), params)
        rows = result.fetchall()
        
        return [
            RetrievalResult(
                id=row.id,
                content=row.content,
                source_type=row.source_type,
                source_id=row.source_id,
                patient_id=row.patient_id,
                keyword_score=float(row.match_score) if row.match_score else 0.0,
                context_date=row.context_date,
                chunk_index=row.chunk_index,
                page_number=row.page_number,
            )
            for row in rows
        ]
    
    async def _structured_search(
        self,
        query_analysis: QueryAnalysis,
        patient_id: int,
        limit: int,
    ) -> list[RetrievalResult]:
        """Query structured data directly for specific queries."""
        results = []
        
        # Search for specific test names in lab results
        if query_analysis.test_names:
            for test_name in query_analysis.test_names:
                query = select(LabResult).where(
                    and_(
                        LabResult.patient_id == patient_id,
                        LabResult.test_name.ilike(f"%{test_name}%"),
                    )
                ).order_by(LabResult.collected_at.desc()).limit(limit)
                
                result = await self.db.execute(query)
                labs = result.scalars().all()
                
                for lab in labs:
                    content = f"Lab: {lab.test_name} = {lab.value}"
                    if lab.unit:
                        content += f" {lab.unit}"
                    if lab.is_abnormal:
                        content += " (ABNORMAL)"
                    
                    results.append(RetrievalResult(
                        id=lab.id,
                        content=content,
                        source_type="lab_result",
                        source_id=lab.id,
                        patient_id=patient_id,
                        keyword_score=0.9,  # High score for direct match
                        context_date=lab.collected_at or lab.resulted_at,
                    ))
        
        # Search for medication names
        if query_analysis.medication_names or DataSource.MEDICATION in query_analysis.data_sources:
            query = select(Medication).where(
                Medication.patient_id == patient_id
            )
            
            if query_analysis.medication_names:
                conditions = [
                    Medication.name.ilike(f"%{name}%")
                    for name in query_analysis.medication_names
                ]
                query = query.where(or_(*conditions))
            
            query = query.order_by(Medication.prescribed_at.desc()).limit(limit)
            
            result = await self.db.execute(query)
            meds = result.scalars().all()
            
            for med in meds:
                content = f"Medication: {med.name}"
                if med.dosage:
                    content += f" {med.dosage}"
                if med.frequency:
                    content += f" ({med.frequency})"
                content += f" - {'Active' if med.is_active else 'Discontinued'}"
                
                results.append(RetrievalResult(
                    id=med.id,
                    content=content,
                    source_type="medication",
                    source_id=med.id,
                    patient_id=patient_id,
                    keyword_score=0.8,
                    context_date=med.prescribed_at,
                ))
        
        return results[:limit]
