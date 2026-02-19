"""Context ranker for re-ranking retrieval results.

Implements advanced re-ranking strategies to improve the quality
of retrieved context before sending to the LLM.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.services.context.analyzer import QueryAnalysis, QueryIntent
from app.services.context.retriever import RetrievalResult


@dataclass
class RankedResult:
    """A re-ranked result with additional scoring metadata."""

    result: RetrievalResult
    final_score: float
    relevance_score: float
    diversity_penalty: float
    position_score: float
    reasoning: str = ""


class ContextRanker:
    """Re-ranks retrieval results for optimal LLM context.

    Ranking strategies:
    1. Relevance: How well the content matches the query
    2. Diversity: Avoid redundant/overlapping content
    3. Recency: Prioritize recent information when appropriate
    4. Source priority: Weight different source types
    5. Coverage: Ensure broad topic coverage
    """

    # Source type priorities for different intents
    SOURCE_PRIORITIES = {
        QueryIntent.LIST: {
            "medication": 1.0,
            "lab_result": 0.8,
            "encounter": 0.6,
            "document": 0.5,
        },
        QueryIntent.VALUE: {
            "lab_result": 1.0,
            "medication": 0.6,
            "encounter": 0.7,
            "document": 0.5,
        },
        QueryIntent.STATUS: {
            "encounter": 1.0,
            "lab_result": 0.9,
            "medication": 0.7,
            "document": 0.6,
        },
        QueryIntent.HISTORY: {
            "encounter": 1.0,
            "document": 0.9,
            "lab_result": 0.7,
            "medication": 0.6,
        },
        QueryIntent.RECENT: {
            "encounter": 1.0,
            "lab_result": 1.0,
            "medication": 0.8,
            "document": 0.7,
        },
        QueryIntent.SUMMARY: {
            "encounter": 1.0,
            "medication": 0.9,
            "lab_result": 0.8,
            "document": 0.7,
        },
    }

    def __init__(
        self,
        diversity_threshold: float = 0.7,
        recency_decay_days: int = 365,
    ):
        """Initialize the ranker.

        Args:
            diversity_threshold: Similarity threshold for diversity penalty
            recency_decay_days: Days over which recency score decays
        """
        self.diversity_threshold = diversity_threshold
        self.recency_decay_days = recency_decay_days

    def rank(
        self,
        results: list[RetrievalResult],
        query_analysis: QueryAnalysis,
        max_results: int = 10,
    ) -> list[RankedResult]:
        """Re-rank results based on query analysis.

        Args:
            results: Initial retrieval results
            query_analysis: Query analysis with intent info
            max_results: Maximum results to return

        Returns:
            List of re-ranked results
        """
        if not results:
            return []

        # Calculate base relevance scores
        scored_results = []
        for result in results:
            relevance = self._calculate_relevance(result, query_analysis)
            scored_results.append((result, relevance))

        # Sort by relevance
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # Apply diversity penalty and build final rankings
        ranked_results = []
        selected_contents: list[str] = []

        for result, relevance in scored_results:
            if len(ranked_results) >= max_results:
                break

            # Calculate diversity penalty
            diversity_penalty = self._calculate_diversity_penalty(
                result.content,
                selected_contents,
            )

            # Skip highly redundant content
            if diversity_penalty > 0.5:
                continue

            # Calculate position score (earlier is better)
            position_score = 1.0 - (len(ranked_results) / max_results)

            # Calculate final score
            final_score = (
                relevance * 0.7 + (1 - diversity_penalty) * 0.2 + position_score * 0.1
            )

            ranked_results.append(
                RankedResult(
                    result=result,
                    final_score=final_score,
                    relevance_score=relevance,
                    diversity_penalty=diversity_penalty,
                    position_score=position_score,
                    reasoning=self._generate_reasoning(result, query_analysis),
                )
            )

            selected_contents.append(result.content.lower())

        # Final sort by final score
        ranked_results.sort(key=lambda x: x.final_score, reverse=True)

        return ranked_results

    def _calculate_relevance(
        self,
        result: RetrievalResult,
        query_analysis: QueryAnalysis,
    ) -> float:
        """Calculate relevance score for a result."""
        # Start with combined score from retrieval
        relevance = max(result.combined_score, result.rerank_score)

        # Apply source priority boost
        source_priorities = self.SOURCE_PRIORITIES.get(
            query_analysis.intent,
            {"lab_result": 0.8, "medication": 0.8, "encounter": 0.8, "document": 0.7},
        )
        source_boost = source_priorities.get(result.source_type, 0.5)
        relevance *= source_boost

        # Boost if content contains query keywords
        content_lower = result.content.lower()
        keyword_matches = sum(
            1 for kw in query_analysis.keywords if kw in content_lower
        )
        if query_analysis.keywords:
            keyword_boost = (
                min(keyword_matches / len(query_analysis.keywords), 1.0) * 0.2
            )
            relevance += keyword_boost

        # Boost for medical entities
        entity_matches = sum(
            1 for entity in query_analysis.medical_entities if entity in content_lower
        )
        if query_analysis.medical_entities:
            entity_boost = (
                min(entity_matches / len(query_analysis.medical_entities), 1.0) * 0.15
            )
            relevance += entity_boost

        # Recency boost for temporal queries
        if query_analysis.boost_recent and result.context_date:
            days_ago = (datetime.now(UTC) - result.context_date).days
            recency_boost = max(0, 1 - (days_ago / self.recency_decay_days)) * 0.15
            relevance += recency_boost

        return min(relevance, 1.0)

    def _calculate_diversity_penalty(
        self,
        content: str,
        selected_contents: list[str],
    ) -> float:
        """Calculate diversity penalty based on similarity to selected content."""
        if not selected_contents:
            return 0.0

        content_lower = content.lower()
        content_words = set(content_lower.split())

        max_overlap = 0.0
        for selected in selected_contents:
            selected_words = set(selected.split())

            # Jaccard similarity
            intersection = len(content_words & selected_words)
            union = len(content_words | selected_words)

            if union > 0:
                overlap = intersection / union
                max_overlap = max(max_overlap, overlap)

        # Apply threshold - no penalty below threshold
        if max_overlap < self.diversity_threshold:
            return 0.0

        return max_overlap

    def _generate_reasoning(
        self,
        result: RetrievalResult,
        query_analysis: QueryAnalysis,
    ) -> str:
        """Generate human-readable reasoning for why this result was selected."""
        reasons = []

        if result.semantic_score > 0.7:
            reasons.append("High semantic relevance")
        elif result.semantic_score > 0.5:
            reasons.append("Good semantic match")

        if result.keyword_score > 0.5:
            reasons.append("Contains query keywords")

        if result.context_date:
            days_ago = (datetime.now(UTC) - result.context_date).days
            if days_ago < 30:
                reasons.append("Recent data")
            elif days_ago < 90:
                reasons.append("From past 3 months")

        source_label = result.source_type.replace("_", " ").title()
        reasons.append(f"Source: {source_label}")

        return "; ".join(reasons) if reasons else "General relevance"

    def rerank_for_coverage(
        self,
        ranked_results: list[RankedResult],
        min_per_source: int = 1,
    ) -> list[RankedResult]:
        """Re-rank to ensure coverage across source types.

        Ensures at least min_per_source results from each available source type.
        """
        # Group by source type
        by_source: dict[str, list[RankedResult]] = {}
        for result in ranked_results:
            source = result.result.source_type
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(result)

        # Build balanced results
        final_results = []
        source_counts: dict[str, int] = {s: 0 for s in by_source}

        # First pass: ensure minimum coverage
        for source, results in by_source.items():
            for result in results[:min_per_source]:
                final_results.append(result)
                source_counts[source] += 1

        # Second pass: fill with remaining by score
        remaining = [r for r in ranked_results if r not in final_results]
        remaining.sort(key=lambda x: x.final_score, reverse=True)

        for result in remaining:
            if len(final_results) >= len(ranked_results):
                break
            final_results.append(result)

        # Sort final results by score
        final_results.sort(key=lambda x: x.final_score, reverse=True)

        return final_results
