"""Context synthesizer for building optimal LLM context.

Takes ranked retrieval results and synthesizes them into
structured context suitable for LLM reasoning.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.services.context.analyzer import QueryAnalysis, QueryIntent
from app.services.context.ranker import RankedResult


@dataclass
class ContextSection:
    """A section of synthesized context."""
    
    title: str
    content: str
    source_type: str
    relevance: float
    date: Optional[datetime] = None


@dataclass
class SynthesizedContext:
    """Complete synthesized context for LLM."""
    
    # The query being answered
    query: str
    
    # Structured context sections
    sections: list[ContextSection] = field(default_factory=list)
    
    # Combined context string
    full_context: str = ""
    
    # Metadata
    total_chunks_used: int = 0
    total_characters: int = 0
    estimated_tokens: int = 0
    source_types_included: list[str] = field(default_factory=list)
    
    # Time range of included data
    earliest_date: Optional[datetime] = None
    latest_date: Optional[datetime] = None


class ContextSynthesizer:
    """Synthesizes retrieved results into optimal LLM context.
    
    Strategies:
    1. Organize by source type for clarity
    2. Add temporal markers for time-aware reasoning
    3. Highlight key information
    4. Stay within token limits
    5. Provide structured format for easier parsing
    """
    
    # Section headers by source type
    SECTION_HEADERS = {
        "lab_result": "📊 Laboratory Results",
        "medication": "💊 Medications",
        "encounter": "🏥 Clinical Encounters",
        "document": "📄 Documents",
        "custom": "📝 Additional Notes",
    }
    
    # Token estimation (rough approximation)
    CHARS_PER_TOKEN = 4
    
    def __init__(
        self,
        max_tokens: int = 4000,
        include_metadata: bool = True,
        include_dates: bool = True,
        group_by_source: bool = True,
    ):
        """Initialize the synthesizer.
        
        Args:
            max_tokens: Maximum tokens in output context
            include_metadata: Include source metadata
            include_dates: Include temporal information
            group_by_source: Group context by source type
        """
        self.max_tokens = max_tokens
        self.include_metadata = include_metadata
        self.include_dates = include_dates
        self.group_by_source = group_by_source
    
    def synthesize(
        self,
        ranked_results: list[RankedResult],
        query_analysis: QueryAnalysis,
    ) -> SynthesizedContext:
        """Synthesize ranked results into LLM-ready context.
        
        Args:
            ranked_results: Ranked retrieval results
            query_analysis: Query analysis for context building
            
        Returns:
            SynthesizedContext ready for LLM
        """
        if not ranked_results:
            return SynthesizedContext(
                query=query_analysis.original_query,
                full_context="No relevant information found in the patient's records.",
            )
        
        # Build context based on strategy
        if self.group_by_source:
            context = self._synthesize_grouped(ranked_results, query_analysis)
        else:
            context = self._synthesize_linear(ranked_results, query_analysis)
        
        return context
    
    def _synthesize_grouped(
        self,
        ranked_results: list[RankedResult],
        query_analysis: QueryAnalysis,
    ) -> SynthesizedContext:
        """Synthesize context grouped by source type."""
        # Group results by source
        by_source: dict[str, list[RankedResult]] = {}
        for result in ranked_results:
            source = result.result.source_type
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(result)
        
        # Build sections
        sections = []
        source_order = ["encounter", "lab_result", "medication", "document", "custom"]
        
        for source in source_order:
            if source not in by_source:
                continue
            
            results = by_source[source]
            section_content = self._build_section_content(results)
            
            if section_content:
                sections.append(ContextSection(
                    title=self.SECTION_HEADERS.get(source, source.title()),
                    content=section_content,
                    source_type=source,
                    relevance=max(r.relevance_score for r in results),
                    date=self._get_latest_date(results),
                ))
        
        # Build full context
        full_context = self._build_full_context(
            sections,
            query_analysis,
            self.max_tokens,
        )
        
        # Calculate metadata
        dates = [
            r.result.context_date
            for r in ranked_results
            if r.result.context_date
        ]
        
        return SynthesizedContext(
            query=query_analysis.original_query,
            sections=sections,
            full_context=full_context,
            total_chunks_used=len(ranked_results),
            total_characters=len(full_context),
            estimated_tokens=len(full_context) // self.CHARS_PER_TOKEN,
            source_types_included=list(by_source.keys()),
            earliest_date=min(dates) if dates else None,
            latest_date=max(dates) if dates else None,
        )
    
    def _synthesize_linear(
        self,
        ranked_results: list[RankedResult],
        query_analysis: QueryAnalysis,
    ) -> SynthesizedContext:
        """Synthesize context in linear order by relevance."""
        parts = []
        total_chars = 0
        max_chars = self.max_tokens * self.CHARS_PER_TOKEN
        
        for i, ranked in enumerate(ranked_results, 1):
            result = ranked.result
            
            # Format entry
            entry = self._format_entry(result)
            
            # Check token limit
            if total_chars + len(entry) > max_chars:
                break
            
            parts.append(entry)
            total_chars += len(entry)
        
        full_context = "\n\n---\n\n".join(parts)
        
        dates = [
            r.result.context_date
            for r in ranked_results
            if r.result.context_date
        ]
        
        return SynthesizedContext(
            query=query_analysis.original_query,
            sections=[],
            full_context=full_context,
            total_chunks_used=len(parts),
            total_characters=len(full_context),
            estimated_tokens=len(full_context) // self.CHARS_PER_TOKEN,
            source_types_included=list(set(r.result.source_type for r in ranked_results)),
            earliest_date=min(dates) if dates else None,
            latest_date=max(dates) if dates else None,
        )
    
    def _build_section_content(
        self,
        results: list[RankedResult],
    ) -> str:
        """Build content for a section."""
        entries = []
        
        for ranked in results:
            result = ranked.result
            entry = self._format_entry(result, include_source=False)
            entries.append(entry)
        
        return "\n\n".join(entries)
    
    def _format_entry(
        self,
        result,
        include_source: bool = True,
    ) -> str:
        """Format a single result entry."""
        parts = []
        
        # Add source label if requested
        if include_source:
            source_label = result.source_type.replace("_", " ").title()
            parts.append(f"[{source_label}]")
        
        # Add date if available
        if self.include_dates and result.context_date:
            date_str = result.context_date.strftime("%Y-%m-%d")
            parts.append(f"({date_str})")
        
        # Add content
        content = result.content.strip()
        
        if parts:
            return f"{' '.join(parts)}\n{content}"
        return content
    
    def _build_full_context(
        self,
        sections: list[ContextSection],
        query_analysis: QueryAnalysis,
        max_tokens: int,
    ) -> str:
        """Build the complete context string."""
        max_chars = max_tokens * self.CHARS_PER_TOKEN
        
        # Build header
        header_parts = [
            "=== Patient Medical Information ===",
            f"Query: {query_analysis.original_query}",
        ]
        
        if query_analysis.temporal.is_temporal:
            time_range = query_analysis.temporal.time_range or "specified"
            header_parts.append(f"Time context: {time_range}")
        
        header = "\n".join(header_parts) + "\n\n"
        total_chars = len(header)
        
        # Add sections within limit
        section_parts = []
        for section in sections:
            section_text = f"--- {section.title} ---\n{section.content}\n"
            
            if total_chars + len(section_text) > max_chars:
                # Try truncating section
                remaining = max_chars - total_chars - 100
                if remaining > 200:
                    truncated = section.content[:remaining] + "...\n[truncated]"
                    section_text = f"--- {section.title} ---\n{truncated}\n"
                    section_parts.append(section_text)
                break
            
            section_parts.append(section_text)
            total_chars += len(section_text)
        
        return header + "\n".join(section_parts)
    
    def _get_latest_date(
        self,
        results: list[RankedResult],
    ) -> Optional[datetime]:
        """Get the latest date from results."""
        dates = [
            r.result.context_date
            for r in results
            if r.result.context_date
        ]
        return max(dates) if dates else None
    
    def create_prompt_context(
        self,
        synthesized: SynthesizedContext,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Create a complete prompt with context for the LLM.
        
        Args:
            synthesized: Synthesized context
            system_prompt: Optional system prompt override
            
        Returns:
            Complete prompt string
        """
        if not system_prompt:
            system_prompt = (
                "You are a medical assistant. Answer concisely using only the provided context. "
                "Do not include reasoning, analysis, or meta commentary. "
                "No greetings or apologies. "
                "If information is not available, respond exactly: \"No information available about [topic].\""
            )
        
        prompt = f"""{system_prompt}

PATIENT CONTEXT:
{synthesized.full_context}

QUESTION: {synthesized.query}

Answer:"""
        
        return prompt
