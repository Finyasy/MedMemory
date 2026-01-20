"""Similarity search service using pgvector.

Performs semantic search over the vector memory to find
relevant medical information for a given query.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import MemoryChunk
from app.services.embeddings.embedding import EmbeddingService


@dataclass
class SearchResult:
    """A single search result with relevance score."""
    
    chunk_id: int
    patient_id: int
    content: str
    source_type: str
    source_id: Optional[int]
    similarity_score: float
    context_date: Optional[datetime]
    chunk_type: Optional[str]
    
    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "patient_id": self.patient_id,
            "content": self.content,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "similarity_score": round(self.similarity_score, 4),
            "context_date": self.context_date.isoformat() if self.context_date else None,
            "chunk_type": self.chunk_type,
        }


@dataclass
class SearchResponse:
    """Response containing search results and metadata."""
    
    query: str
    results: list[SearchResult]
    total_results: int
    search_time_ms: float
    
    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "total_results": self.total_results,
            "search_time_ms": round(self.search_time_ms, 2),
        }


class SimilaritySearchService:
    """Service for semantic similarity search.
    
    Uses pgvector's cosine similarity to find the most relevant
    memory chunks for a given query.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        """Initialize the search service.
        
        Args:
            db: Database session
            embedding_service: Service for generating query embeddings
        """
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService.get_instance()
    
    async def search(
        self,
        query: str,
        patient_id: Optional[int] = None,
        source_types: Optional[list[str]] = None,
        limit: int = 10,
        min_similarity: float = 0.3,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> SearchResponse:
        """Search for similar content in vector memory.
        
        Args:
            query: Search query text
            patient_id: Filter by specific patient
            source_types: Filter by source types (lab_result, medication, etc.)
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold (0-1)
            date_from: Filter by date range start
            date_to: Filter by date range end
            
        Returns:
            SearchResponse with ranked results
        """
        import time
        start_time = time.time()
        
        # Generate query embedding
        query_embedding = await self.embedding_service.embed_query_async(query)
        
        # Build the SQL query using pgvector cosine similarity
        # 1 - (embedding <=> query_embedding) gives similarity (1 = identical, 0 = orthogonal)
        # Use CAST() instead of :: syntax for asyncpg compatibility
        sql = """
            SELECT 
                id,
                patient_id,
                content,
                source_type,
                source_id,
                context_date,
                chunk_type,
                1 - (embedding <=> CAST(:query_embedding AS vector)) as similarity
            FROM memory_chunks
            WHERE is_indexed = true
            AND 1 - (embedding <=> CAST(:query_embedding AS vector)) >= :min_similarity
        """
        
        params = {
            "query_embedding": str(query_embedding),
            "min_similarity": min_similarity,
        }
        
        # Add filters
        if patient_id:
            sql += " AND patient_id = :patient_id"
            params["patient_id"] = patient_id
        
        if source_types:
            sql += " AND source_type = ANY(:source_types)"
            params["source_types"] = source_types
        
        if date_from:
            sql += " AND (context_date IS NULL OR context_date >= :date_from)"
            params["date_from"] = date_from
        
        if date_to:
            sql += " AND (context_date IS NULL OR context_date <= :date_to)"
            params["date_to"] = date_to
        
        # Order by similarity and limit
        sql += " ORDER BY similarity DESC LIMIT :limit"
        params["limit"] = limit
        
        # Execute query
        result = await self.db.execute(text(sql), params)
        rows = result.fetchall()
        
        # Build results
        results = [
            SearchResult(
                chunk_id=row.id,
                patient_id=row.patient_id,
                content=row.content,
                source_type=row.source_type,
                source_id=row.source_id,
                similarity_score=float(row.similarity),
                context_date=row.context_date,
                chunk_type=row.chunk_type,
            )
            for row in rows
        ]
        
        search_time = (time.time() - start_time) * 1000
        
        return SearchResponse(
            query=query,
            results=results,
            total_results=len(results),
            search_time_ms=search_time,
        )
    
    async def search_patient_history(
        self,
        patient_id: int,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.3,
    ) -> SearchResponse:
        """Search within a specific patient's medical history.
        
        Args:
            patient_id: Patient to search
            query: Search query
            limit: Maximum results
            min_similarity: Similarity threshold
            
        Returns:
            SearchResponse with relevant patient records
        """
        return await self.search(
            query=query,
            patient_id=patient_id,
            limit=limit,
            min_similarity=min_similarity,
        )
    
    async def find_similar_chunks(
        self,
        chunk_id: int,
        limit: int = 5,
        same_patient_only: bool = True,
    ) -> list[SearchResult]:
        """Find chunks similar to a given chunk.
        
        Useful for finding related information or context.
        
        Args:
            chunk_id: Source chunk to find similar content for
            limit: Maximum results
            same_patient_only: Only search within same patient
            
        Returns:
            List of similar chunks
        """
        # Get the source chunk
        result = await self.db.execute(
            select(MemoryChunk).where(MemoryChunk.id == chunk_id)
        )
        source_chunk = result.scalar_one_or_none()
        
        if not source_chunk or not source_chunk.embedding:
            return []
        
        # Search for similar chunks
        # Use CAST() instead of :: syntax for asyncpg compatibility
        sql = """
            SELECT 
                id,
                patient_id,
                content,
                source_type,
                source_id,
                context_date,
                chunk_type,
                1 - (embedding <=> CAST(:query_embedding AS vector)) as similarity
            FROM memory_chunks
            WHERE is_indexed = true
            AND id != :chunk_id
        """
        
        params = {
            "query_embedding": str(source_chunk.embedding),
            "chunk_id": chunk_id,
        }
        
        if same_patient_only:
            sql += " AND patient_id = :patient_id"
            params["patient_id"] = source_chunk.patient_id
        
        sql += " ORDER BY similarity DESC LIMIT :limit"
        params["limit"] = limit
        
        result = await self.db.execute(text(sql), params)
        rows = result.fetchall()
        
        return [
            SearchResult(
                chunk_id=row.id,
                patient_id=row.patient_id,
                content=row.content,
                source_type=row.source_type,
                source_id=row.source_id,
                similarity_score=float(row.similarity),
                context_date=row.context_date,
                chunk_type=row.chunk_type,
            )
            for row in rows
        ]
    
    async def get_patient_context(
        self,
        patient_id: int,
        query: str,
        max_chunks: int = 10,
        max_tokens: int = 2000,
    ) -> str:
        """Get relevant context for a patient query.
        
        This is optimized for feeding into an LLM for Q&A.
        Returns concatenated relevant chunks within token limits.
        
        Args:
            patient_id: Patient to get context for
            query: The question being asked
            max_chunks: Maximum number of chunks
            max_tokens: Approximate token limit
            
        Returns:
            Concatenated context string
        """
        # Search for relevant chunks
        response = await self.search_patient_history(
            patient_id=patient_id,
            query=query,
            limit=max_chunks,
            min_similarity=settings.similarity_threshold,
        )
        
        if not response.results:
            return ""
        
        # Build context string
        context_parts = []
        total_chars = 0
        approx_chars_per_token = 4  # Rough estimate
        max_chars = max_tokens * approx_chars_per_token
        
        for result in response.results:
            # Format the chunk
            source_label = result.source_type.replace("_", " ").title()
            date_str = ""
            if result.context_date:
                date_str = f" ({result.context_date.strftime('%Y-%m-%d')})"
            
            chunk_text = f"[{source_label}{date_str}]\n{result.content}"
            
            # Check if we're within limits
            if total_chars + len(chunk_text) > max_chars:
                break
            
            context_parts.append(chunk_text)
            total_chars += len(chunk_text)
        
        return "\n\n---\n\n".join(context_parts)
    
    async def count_indexed_chunks(
        self,
        patient_id: Optional[int] = None,
    ) -> dict:
        """Get statistics about indexed chunks.
        
        Args:
            patient_id: Optional filter by patient
            
        Returns:
            Dictionary with count statistics
        """
        from sqlalchemy import func
        
        base_query = select(
            MemoryChunk.source_type,
            func.count(MemoryChunk.id).label("count"),
        ).where(MemoryChunk.is_indexed == True)
        
        if patient_id:
            base_query = base_query.where(MemoryChunk.patient_id == patient_id)
        
        base_query = base_query.group_by(MemoryChunk.source_type)
        
        result = await self.db.execute(base_query)
        rows = result.fetchall()
        
        counts = {row.source_type: row.count for row in rows}
        counts["total"] = sum(counts.values())
        
        return counts
