"""Shared vector search query builder for pgvector.

Centralizes the SQL query construction for similarity search
to ensure consistency across retriever and search services.
"""

from dataclasses import dataclass, field


@dataclass
class VectorSearchQuery:
    """Builder for vector similarity search queries.

    Uses pgvector's cosine distance operator (<=>)  with CAST() syntax
    for asyncpg compatibility.
    """

    query_embedding: list[float]
    patient_id: int | None = None
    min_similarity: float = 0.0
    exclude_chunk_id: int | None = None
    source_types: list[str] | None = None
    limit: int = 10
    include_chunk_type: bool = True
    extra_columns: list[str] = field(default_factory=list)

    # Column selection presets
    BASE_COLUMNS = [
        "id",
        "patient_id",
        "content",
        "source_type",
        "source_id",
        "context_date",
    ]

    def build(self) -> tuple[str, dict]:
        """Build the SQL query and parameters.

        Returns:
            Tuple of (sql_query, params_dict)
        """
        # Build column list
        columns = self.BASE_COLUMNS.copy()
        if self.include_chunk_type:
            columns.append("chunk_type")
        columns.extend(self.extra_columns)

        # Add similarity calculation
        columns.append(
            "1 - (embedding <=> CAST(:query_embedding AS vector)) as similarity"
        )

        column_str = ",\n                ".join(columns)

        # Build WHERE clause
        conditions = ["is_indexed = true"]
        params = {"query_embedding": str(self.query_embedding)}

        if self.patient_id is not None:
            conditions.append("patient_id = :patient_id")
            params["patient_id"] = self.patient_id

        if self.min_similarity > 0:
            conditions.append(
                "1 - (embedding <=> CAST(:query_embedding AS vector)) >= :min_similarity"
            )
            params["min_similarity"] = self.min_similarity

        if self.exclude_chunk_id is not None:
            conditions.append("id != :exclude_chunk_id")
            params["exclude_chunk_id"] = self.exclude_chunk_id

        if self.source_types:
            conditions.append("source_type = ANY(:source_types)")
            params["source_types"] = self.source_types

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT 
                {column_str}
            FROM memory_chunks
            WHERE {where_clause}
            ORDER BY similarity DESC
            LIMIT :limit
        """
        params["limit"] = self.limit

        return sql, params


def build_similarity_search(
    query_embedding: list[float],
    patient_id: int | None = None,
    min_similarity: float = 0.0,
    limit: int = 10,
    source_types: list[str] | None = None,
    exclude_chunk_id: int | None = None,
    include_chunk_type: bool = True,
) -> tuple[str, dict]:
    """Convenience function to build a similarity search query.

    Args:
        query_embedding: The embedding vector to search for
        patient_id: Filter by patient ID (optional)
        min_similarity: Minimum similarity threshold (0-1)
        limit: Maximum number of results
        source_types: Filter by source types (optional)
        exclude_chunk_id: Exclude a specific chunk ID
        include_chunk_type: Include chunk_type in results

    Returns:
        Tuple of (sql_query, params_dict)
    """
    builder = VectorSearchQuery(
        query_embedding=query_embedding,
        patient_id=patient_id,
        min_similarity=min_similarity,
        limit=limit,
        source_types=source_types,
        exclude_chunk_id=exclude_chunk_id,
        include_chunk_type=include_chunk_type,
    )
    return builder.build()
