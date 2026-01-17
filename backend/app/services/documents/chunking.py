"""Text chunking service for document processing.

Breaks down documents into smaller, semantically meaningful chunks
for embedding and retrieval.
"""

import hashlib
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class TextChunk:
    """A chunk of text from a document."""
    
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    page_number: Optional[int] = None
    metadata: Optional[dict] = None
    
    @property
    def content_hash(self) -> str:
        """Generate hash of chunk content for deduplication."""
        return hashlib.sha256(self.content.encode()).hexdigest()
    
    @property
    def word_count(self) -> int:
        """Count words in chunk."""
        return len(self.content.split())


class TextChunker:
    """Service for chunking text into smaller pieces.
    
    Implements intelligent text splitting that:
    - Respects sentence and paragraph boundaries
    - Maintains semantic coherence
    - Creates overlapping chunks for better retrieval
    - Handles medical text patterns (sections, headers)
    """
    
    # Common section headers in medical documents
    MEDICAL_HEADERS = [
        r"(?:^|\n)(CHIEF COMPLAINT|CC):?",
        r"(?:^|\n)(HISTORY OF PRESENT ILLNESS|HPI):?",
        r"(?:^|\n)(PAST MEDICAL HISTORY|PMH):?",
        r"(?:^|\n)(MEDICATIONS|CURRENT MEDICATIONS):?",
        r"(?:^|\n)(ALLERGIES):?",
        r"(?:^|\n)(FAMILY HISTORY|FH):?",
        r"(?:^|\n)(SOCIAL HISTORY|SH):?",
        r"(?:^|\n)(REVIEW OF SYSTEMS|ROS):?",
        r"(?:^|\n)(PHYSICAL EXAM|PE|EXAMINATION):?",
        r"(?:^|\n)(VITAL SIGNS|VITALS):?",
        r"(?:^|\n)(ASSESSMENT|IMPRESSION):?",
        r"(?:^|\n)(PLAN|TREATMENT PLAN):?",
        r"(?:^|\n)(LABORATORY|LAB RESULTS|LABS):?",
        r"(?:^|\n)(IMAGING|RADIOLOGY):?",
        r"(?:^|\n)(DIAGNOSIS|DIAGNOSES):?",
        r"(?:^|\n)(RECOMMENDATIONS):?",
        r"(?:^|\n)(FOLLOW-UP|FOLLOW UP):?",
        r"--- Page \d+ ---",  # Page markers
    ]
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
        respect_sentences: bool = True,
        respect_sections: bool = True,
    ):
        """Initialize the chunker.
        
        Args:
            chunk_size: Target size for each chunk (in characters)
            chunk_overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum chunk size (smaller chunks are merged)
            respect_sentences: Try to split at sentence boundaries
            respect_sections: Try to split at section headers
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.respect_sentences = respect_sentences
        self.respect_sections = respect_sections
        
        # Compile header pattern
        self.header_pattern = re.compile(
            "|".join(self.MEDICAL_HEADERS),
            re.IGNORECASE | re.MULTILINE,
        )
    
    def chunk_text(
        self,
        text: str,
        source_type: str = "document",
    ) -> list[TextChunk]:
        """Chunk text into smaller pieces.
        
        Args:
            text: Full text to chunk
            source_type: Type of source (affects chunking strategy)
            
        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            return []
        
        # Normalize whitespace
        text = self._normalize_text(text)
        
        # Split by sections first if enabled
        if self.respect_sections:
            sections = self._split_by_sections(text)
        else:
            sections = [text]
        
        # Chunk each section
        chunks = []
        global_char_offset = 0
        
        for section in sections:
            section_chunks = self._chunk_section(
                section,
                start_offset=global_char_offset,
                start_index=len(chunks),
            )
            chunks.extend(section_chunks)
            global_char_offset += len(section)
        
        # Merge small chunks
        chunks = self._merge_small_chunks(chunks)
        
        # Reindex after merging
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
        
        return chunks
    
    def chunk_by_pages(
        self,
        text: str,
        page_separator: str = r"--- Page \d+ ---",
    ) -> list[TextChunk]:
        """Chunk text that has page markers.
        
        Args:
            text: Text with page markers
            page_separator: Regex pattern for page separators
            
        Returns:
            List of TextChunk objects with page numbers
        """
        # Split by page markers
        pages = re.split(page_separator, text)
        
        chunks = []
        for page_num, page_text in enumerate(pages, 1):
            if not page_text.strip():
                continue
            
            # Chunk the page
            page_chunks = self.chunk_text(page_text)
            
            # Add page number to each chunk
            for chunk in page_chunks:
                chunk.page_number = page_num
                chunk.chunk_index = len(chunks)
                chunks.append(chunk)
        
        return chunks
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text whitespace and formatting."""
        # Replace multiple newlines with double newline
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        # Replace multiple spaces with single space
        text = re.sub(r" {2,}", " ", text)
        
        # Strip leading/trailing whitespace from lines
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)
        
        return text.strip()
    
    def _split_by_sections(self, text: str) -> list[str]:
        """Split text by section headers."""
        # Find all header positions
        matches = list(self.header_pattern.finditer(text))
        
        if not matches:
            return [text]
        
        sections = []
        prev_end = 0
        
        for match in matches:
            # Add text before this header
            if match.start() > prev_end:
                section = text[prev_end:match.start()].strip()
                if section:
                    sections.append(section)
            prev_end = match.start()
        
        # Add remaining text
        if prev_end < len(text):
            section = text[prev_end:].strip()
            if section:
                sections.append(section)
        
        return sections if sections else [text]
    
    def _chunk_section(
        self,
        text: str,
        start_offset: int = 0,
        start_index: int = 0,
    ) -> list[TextChunk]:
        """Chunk a section of text."""
        if len(text) <= self.chunk_size:
            return [TextChunk(
                content=text,
                chunk_index=start_index,
                start_char=start_offset,
                end_char=start_offset + len(text),
            )]
        
        chunks = []
        current_pos = 0
        chunk_index = start_index
        
        while current_pos < len(text):
            # Determine end position for this chunk
            end_pos = min(current_pos + self.chunk_size, len(text))
            
            # If not at the end, try to find a good break point
            if end_pos < len(text) and self.respect_sentences:
                end_pos = self._find_break_point(text, current_pos, end_pos)
            
            # Extract chunk text
            chunk_text = text[current_pos:end_pos].strip()
            
            if chunk_text:
                chunks.append(TextChunk(
                    content=chunk_text,
                    chunk_index=chunk_index,
                    start_char=start_offset + current_pos,
                    end_char=start_offset + end_pos,
                ))
                chunk_index += 1
            
            # Move position with overlap
            current_pos = end_pos - self.chunk_overlap
            if current_pos <= chunks[-1].start_char - start_offset if chunks else 0:
                current_pos = end_pos  # Prevent infinite loop
        
        return chunks
    
    def _find_break_point(
        self,
        text: str,
        start: int,
        target: int,
    ) -> int:
        """Find a good break point near the target position.
        
        Prefers breaks at:
        1. Paragraph boundaries (double newline)
        2. Sentence boundaries (. ! ?)
        3. Clause boundaries (, ; :)
        4. Word boundaries (space)
        """
        search_range = min(100, target - start)  # Look back up to 100 chars
        search_text = text[target - search_range:target]
        
        # Try paragraph break
        para_break = search_text.rfind("\n\n")
        if para_break >= 0:
            return target - search_range + para_break + 2
        
        # Try sentence break
        for punct in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
            sent_break = search_text.rfind(punct)
            if sent_break >= 0:
                return target - search_range + sent_break + len(punct)
        
        # Try clause break
        for punct in [", ", "; ", ": ", ",\n", ";\n"]:
            clause_break = search_text.rfind(punct)
            if clause_break >= 0:
                return target - search_range + clause_break + len(punct)
        
        # Fall back to word break
        space_break = search_text.rfind(" ")
        if space_break >= 0:
            return target - search_range + space_break + 1
        
        # If no good break found, use target position
        return target
    
    def _merge_small_chunks(self, chunks: list[TextChunk]) -> list[TextChunk]:
        """Merge chunks smaller than minimum size."""
        if not chunks:
            return chunks
        
        merged = []
        current = chunks[0]
        
        for next_chunk in chunks[1:]:
            if len(current.content) < self.min_chunk_size:
                # Merge with next chunk
                current = TextChunk(
                    content=current.content + "\n\n" + next_chunk.content,
                    chunk_index=current.chunk_index,
                    start_char=current.start_char,
                    end_char=next_chunk.end_char,
                    page_number=current.page_number,
                )
            else:
                merged.append(current)
                current = next_chunk
        
        merged.append(current)
        return merged
    
    def create_chunks_for_record(
        self,
        record_type: str,
        record_id: int,
        text: str,
        context_date: Optional[str] = None,
    ) -> list[dict]:
        """Create chunk dictionaries ready for database insertion.
        
        Args:
            record_type: Type of source record (lab_result, medication, etc.)
            record_id: ID of the source record
            text: Text to chunk
            context_date: Date for temporal context
            
        Returns:
            List of dictionaries ready for MemoryChunk creation
        """
        chunks = self.chunk_text(text, source_type=record_type)
        
        return [
            {
                "content": chunk.content,
                "content_hash": chunk.content_hash,
                "source_type": record_type,
                "source_id": record_id,
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "context_date": context_date,
            }
            for chunk in chunks
        ]
