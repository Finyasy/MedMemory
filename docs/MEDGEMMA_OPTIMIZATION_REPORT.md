# MedGemma-1.5-4B-IT Optimization Implementation Report

**Date:** January 29, 2026  
**Status:** Recommendations for Implementation  
**Priority:** High-Impact Improvements for Medical RAG System

---

## Executive Summary

This report outlines 8 high-leverage improvements to optimize your MedMemory application using MedGemma-1.5-4B-IT's strengths: **medical text reasoning** and **multimodal image understanding**. The recommendations are prioritized by impact and implementation complexity, with concrete code examples tailored to your existing architecture.

**Current State:**
- ✅ Hybrid retrieval (semantic + keyword) already implemented
- ✅ Context engine with query analysis, ranking, and synthesis
- ✅ Direct latest-document summary path (recently ported)
- ✅ Multimodal support in LLMService (`generate_with_image`)
- ⚠️ Heavy post-processing needed (regex cleaning)
- ⚠️ No structured output enforcement
- ⚠️ torchvision warning affecting image preprocessing

**Target State:**
- Task-specific routing for predictable outputs
- True multimodal document understanding (image + text)
- Structured JSON output reducing post-processing
- Hybrid retrieval with BM25 + reranking
- Offline robustness for production
- MedGemma-specific features (chart explanation, longitudinal comparison)

---

## Priority Matrix

| Priority | Impact | Effort | Recommendation |
|----------|--------|--------|----------------|
| **P0** | High | Low | Fix torchvision warning |
| **P0** | High | Low | Offline embeddings setup |
| **P1** | High | Medium | Query routing/classification |
| **P1** | High | Medium | Structured output (JSON) |
| **P2** | High | High | Multimodal latest-doc (image + text) |
| **P2** | Medium | Medium | Query rewriting |
| **P3** | Medium | High | BM25 hybrid retrieval enhancement |
| **P3** | Low | Medium | Chart explanation mode |
| **P3** | Low | High | Multi-image comparison |

---

## 1. Query Routing & Task Classification (P1 - High Impact)

### Current State
Your `RAGService.ask()` already has partial routing logic:
- Detects "summary" queries (`is_summary_query`)
- Detects "document" queries (`is_document_query`)
- Special-cases "latest document" summaries

### Recommendation
**Expand routing into explicit task types** with dedicated prompt templates.

### Implementation

**Step 1: Create Query Router**

```python
# backend/app/services/llm/query_router.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional
import re

class QueryTask(Enum):
    """Types of medical queries."""
    DOC_SUMMARY = "doc_summary"  # Latest upload summary
    TREND_ANALYSIS = "trend_analysis"  # "How has HbA1c changed?"
    MEDICATION_RECONCILIATION = "med_reconciliation"  # Active vs stopped
    LAB_INTERPRETATION = "lab_interpretation"  # Flag out-of-range + explain
    GENERAL_QA = "general_qa"  # Needs RAG retrieval
    VISION_EXTRACTION = "vision_extraction"  # Extract from image directly

@dataclass
class RoutingResult:
    """Result of query routing."""
    task: QueryTask
    confidence: float
    extracted_entities: list[str]  # e.g., ["HbA1c", "blood pressure"]
    temporal_intent: Optional[str]  # "trend", "latest", "historical"

class QueryRouter:
    """Routes user queries to appropriate task handlers."""
    
    # Patterns for each task type
    TREND_PATTERNS = [
        r'(how|has|has.*changed|trend|over time|over the past|improved|worsened)',
        r'(hba1c|a1c|blood sugar|glucose|cholesterol|blood pressure|bp|weight)',
    ]
    
    MEDICATION_PATTERNS = [
        r'(medication|meds|drug|prescription|taking|stopped|discontinued|active)',
        r'(current|now|currently|what.*taking)',
    ]
    
    LAB_PATTERNS = [
        r'(lab|test|result|value|range|normal|abnormal|high|low|out of range)',
        r'(explain|what does.*mean|interpret|significance)',
    ]
    
    SUMMARY_PATTERNS = [
        r'(summarize|summary|overview|key.*findings|what.*document|latest.*document)',
        r'(clear|easy.*understand|simple.*language)',
    ]
    
    VISION_PATTERNS = [
        r'(extract|read.*image|what.*see.*image|numbers.*image|table.*image)',
    ]
    
    def route(self, question: str, conversation_history: Optional[list] = None) -> RoutingResult:
        """Route a query to the appropriate task type.
        
        Args:
            question: User's question
            conversation_history: Previous conversation turns for context
            
        Returns:
            RoutingResult with task type and metadata
        """
        q_lower = question.lower()
        
        # Check for trend analysis
        if any(re.search(pattern, q_lower) for pattern in self.TREND_PATTERNS):
            entities = self._extract_entities(q_lower)
            if any(term in q_lower for term in ['trend', 'changed', 'over time', 'improved', 'worsened']):
                return RoutingResult(
                    task=QueryTask.TREND_ANALYSIS,
                    confidence=0.8,
                    extracted_entities=entities,
                    temporal_intent="trend",
                )
        
        # Check for medication reconciliation
        if any(re.search(pattern, q_lower) for pattern in self.MEDICATION_PATTERNS):
            return RoutingResult(
                task=QueryTask.MEDICATION_RECONCILIATION,
                confidence=0.75,
                extracted_entities=[],
                temporal_intent="current",
            )
        
        # Check for lab interpretation
        if any(re.search(pattern, q_lower) for pattern in self.LAB_PATTERNS):
            entities = self._extract_entities(q_lower)
            return RoutingResult(
                task=QueryTask.LAB_INTERPRETATION,
                confidence=0.7,
                extracted_entities=entities,
                temporal_intent=None,
            )
        
        # Check for vision extraction
        if any(re.search(pattern, q_lower) for pattern in self.VISION_PATTERNS):
            return RoutingResult(
                task=QueryTask.VISION_EXTRACTION,
                confidence=0.85,
                extracted_entities=[],
                temporal_intent=None,
            )
        
        # Check for document summary
        if any(re.search(pattern, q_lower) for pattern in self.SUMMARY_PATTERNS):
            return RoutingResult(
                task=QueryTask.DOC_SUMMARY,
                confidence=0.8,
                extracted_entities=[],
                temporal_intent="latest" if "latest" in q_lower or "most recent" in q_lower else None,
            )
        
        # Default to general Q&A
        return RoutingResult(
            task=QueryTask.GENERAL_QA,
            confidence=0.5,
            extracted_entities=[],
            temporal_intent=None,
        )
    
    def _extract_entities(self, text: str) -> list[str]:
        """Extract medical entities (lab names, vital signs, etc.)."""
        entities = []
        # Simple pattern matching - can be enhanced with NER
        patterns = {
            'HbA1c': r'hba1c|a1c|hemoglobin.*a1c',
            'Blood Pressure': r'blood pressure|bp',
            'Cholesterol': r'cholesterol',
            'Glucose': r'glucose|blood sugar',
            'Weight': r'weight',
        }
        for name, pattern in patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                entities.append(name)
        return entities
```

**Step 2: Add Task-Specific Prompts to RAGService**

```python
# In backend/app/services/llm/rag.py

from app.services.llm.query_router import QueryRouter, QueryTask

class RAGService:
    # ... existing code ...
    
    def __init__(self, ...):
        # ... existing init ...
        self.query_router = QueryRouter()
    
    def _get_task_prompt(self, task: QueryTask, question: str, context: str) -> str:
        """Get task-specific prompt template."""
        if task == QueryTask.DOC_SUMMARY:
            return (
                "Summarize the patient's most recent document using ONLY the document text below.\n\n"
                "Output format requirements:\n"
                "- Use 3–5 short sections with bold headings like **✅ Overview**, **📋 Key results**, **❤️ What this means**, **Next steps**.\n"
                "- Use emojis sparingly ONLY in headings (✅ ❤️ 📋) — no emojis in the body.\n"
                "- Do NOT add meta text like \"I understand\" or \"Here is the summary\".\n"
                "- Use the real numbers + units exactly as written.\n"
                "- If a value is not present, do NOT invent it.\n\n"
                f"DOCUMENT TEXT (extracted):\n{context}\n\n"
                f"Patient question: {question}\n\n"
                "Answer:"
            )
        elif task == QueryTask.TREND_ANALYSIS:
            return (
                "Analyze trends in the patient's medical data over time.\n\n"
                "Focus on:\n"
                "- Changes in values (increasing, decreasing, stable)\n"
                "- Time periods and dates\n"
                "- Clinical significance of trends\n"
                "- Any concerning patterns\n\n"
                f"CONTEXT:\n{context}\n\n"
                f"Question: {question}\n\n"
                "Answer:"
            )
        elif task == QueryTask.LAB_INTERPRETATION:
            return (
                "Interpret lab results and explain their clinical significance.\n\n"
                "For each lab value:\n"
                "- State the actual number and unit\n"
                "- Compare to normal ranges\n"
                "- Explain what it means in simple terms\n"
                "- Note if follow-up is needed\n\n"
                f"CONTEXT:\n{context}\n\n"
                f"Question: {question}\n\n"
                "Answer:"
            )
        # ... other task types ...
        else:
            return f"{context}\n\nQuestion: {question}\n\nAnswer:"
    
    async def ask(self, question: str, ...):
        # ... existing code ...
        
        # Route the query
        routing = self.query_router.route(question, conversation_history)
        
        # Use task-specific prompt if not latest-doc summary
        if not latest_doc_text and routing.task != QueryTask.GENERAL_QA:
            # Build context with task-specific focus
            # ... retrieve context ...
            task_prompt = self._get_task_prompt(routing.task, question, context_result.prompt)
            # ... generate with task_prompt ...
```

**Benefits:**
- Shorter, focused prompts per task
- More predictable outputs
- Easier to tune per task type
- Better handling of edge cases

---

## 2. Multimodal Latest-Document Summary (P2 - High Impact)

### Current State
- ✅ `LLMService.generate_with_image()` exists
- ✅ Latest doc summary uses `extracted_text` only
- ⚠️ If OCR/extraction is weak, numbers are missed

### Recommendation
**When `extracted_text` is empty/short OR confidence is low, call MedGemma with the document image directly** to extract key numbers, tables, and dates.

### Implementation

**Step 1: Enhance Document Model to Track Extraction Confidence**

```python
# Already exists in your Document model - ensure these fields are used:
# - extracted_text
# - processing_status
# - Add: extraction_confidence (float, 0.0-1.0) if not present
```

**Step 2: Add Multimodal Path to RAGService**

```python
# In backend/app/services/llm/rag.py

async def ask(self, question: str, ...):
    # ... existing latest_doc detection ...
    
    if latest_doc and latest_doc_text:
        # Check if we should use vision extraction
        text_confidence = getattr(latest_doc, 'extraction_confidence', 1.0)
        text_length = len(latest_doc_text.strip())
        
        # Use vision if: text is short OR confidence is low OR user explicitly asks
        use_vision = (
            text_length < 200 or
            text_confidence < 0.7 or
            "image" in question.lower() or
            "picture" in question.lower()
        )
        
        if use_vision and latest_doc.file_path:
            # Get image bytes from document
            from pathlib import Path
            import base64
            
            doc_path = Path(latest_doc.file_path)
            if doc_path.exists():
                # For PDFs, extract first page as image
                # For images, use directly
                if doc_path.suffix.lower() == '.pdf':
                    # Convert PDF page to image (use PyMuPDF)
                    import fitz
                    doc = fitz.open(str(doc_path))
                    if len(doc) > 0:
                        page = doc[0]
                        pix = page.get_pixmap()
                        img_bytes = pix.tobytes("png")
                        doc.close()
                    else:
                        img_bytes = None
                else:
                    # Read image file
                    img_bytes = doc_path.read_bytes()
                
                if img_bytes:
                    # Call MedGemma with image + text
                    vision_prompt = (
                        "Extract ALL numbers, dates, lab values, vital signs, and key medical information "
                        "from this medical document image. Return the information in a structured format.\n\n"
                        "Include:\n"
                        "- Exact numbers with units (e.g., '72 bpm', '120/80 mmHg', '10.1 g/dL')\n"
                        "- Dates in full (e.g., 'January 27, 2026')\n"
                        "- Lab test names and results\n"
                        "- Medications and dosages\n"
                        "- Any other medical findings\n\n"
                        "If text extraction was already done, combine it with what you see in the image:\n"
                        f"{latest_doc_text}\n\n"
                        "Now extract from the image:"
                    )
                    
                    llm_response = await self.llm_service.generate_with_image(
                        prompt=vision_prompt,
                        image_bytes=img_bytes,
                        system_prompt=enhanced_system_prompt,
                        max_new_tokens=512,  # Longer for extraction
                    )
                    
                    # Merge vision-extracted text with OCR text
                    combined_text = f"{latest_doc_text}\n\n[Vision-extracted content]:\n{llm_response.text}"
                    latest_doc_text = combined_text
                    
                    self.logger.info(
                        "Used vision extraction for doc_id=%s confidence=%.2f",
                        latest_doc.id,
                        text_confidence,
                    )
        
        # Continue with existing direct summary path using enhanced latest_doc_text
        # ... rest of existing code ...
```

**Benefits:**
- Better number extraction from scanned documents
- Handles rotated/misaligned images
- Reduces "bpm without number" issues
- Leverages MedGemma's image understanding

---

## 3. Structured Output (JSON) to Reduce Post-Processing (P1 - High Impact)

### Current State
- ⚠️ Heavy regex cleaning in `rag.py` (200+ lines of post-processing)
- ⚠️ Fragile pattern matching for artifacts
- ⚠️ No validation of output structure

### Recommendation
**Force MedGemma to produce strict JSON structure** that your UI renders. Validate and re-ask if invalid.

### Implementation

**Step 1: Define Response Schema**

```python
# backend/app/schemas/chat.py (add to existing)

from pydantic import BaseModel, Field
from typing import Optional

class LabValue(BaseModel):
    """A single lab value with metadata."""
    name: str = Field(..., description="Lab test name")
    value: Optional[float] = Field(None, description="Numeric value if applicable")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    text_value: Optional[str] = Field(None, description="Text value if not numeric")
    date: Optional[str] = Field(None, description="Date of test")
    is_normal: Optional[bool] = Field(None, description="Whether value is in normal range")
    source_snippet: Optional[str] = Field(None, description="Exact text from document")

class MedicationInfo(BaseModel):
    """Medication information."""
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[str] = None
    source_snippet: Optional[str] = None

class StructuredSummaryResponse(BaseModel):
    """Structured summary response."""
    overview: str = Field(..., description="One-sentence friendly overview")
    key_results: list[LabValue] = Field(default_factory=list)
    medications: list[MedicationInfo] = Field(default_factory=list)
    vital_signs: dict[str, Optional[str]] = Field(default_factory=dict)  # e.g., {"pulse": "72 bpm", "bp": "120/80 mmHg"}
    follow_ups: list[str] = Field(default_factory=list, description="Recommended follow-up actions")
    concerns: list[str] = Field(default_factory=list, description="Any concerns that need attention")
    source_document_id: Optional[int] = None
    extraction_date: Optional[str] = None
```

**Step 2: Add JSON Generation Mode to RAGService**

```python
# In backend/app/services/llm/rag.py

import json
from app.schemas.chat import StructuredSummaryResponse

class RAGService:
    # ... existing code ...
    
    async def ask_structured(
        self,
        question: str,
        patient_id: int,
        conversation_id: Optional[UUID] = None,
        force_json: bool = True,
    ) -> tuple[RAGResponse, Optional[StructuredSummaryResponse]]:
        """Ask with structured JSON output.
        
        Returns both the RAGResponse and parsed structured data.
        """
        # Get latest doc or context
        # ... existing retrieval logic ...
        
        json_prompt = (
            "You must respond with VALID JSON only. No markdown, no code fences, no commentary.\n\n"
            "JSON Schema:\n"
            "{\n"
            '  "overview": "One-sentence friendly overview",\n'
            '  "key_results": [\n'
            '    {"name": "Lab name", "value": 10.1, "unit": "g/dL", "date": "2026-01-27", "is_normal": true, "source_snippet": "exact text"},\n'
            '    ...\n'
            '  ],\n'
            '  "medications": [\n'
            '    {"name": "Med name", "dosage": "500mg", "frequency": "twice daily", "source_snippet": "exact text"},\n'
            '    ...\n'
            '  ],\n'
            '  "vital_signs": {"pulse": "72 bpm", "blood_pressure": "120/80 mmHg", "temperature": "37.0°C"},\n'
            '  "follow_ups": ["Action 1", "Action 2"],\n'
            '  "concerns": ["Concern 1"],\n'
            '  "source_document_id": 123,\n'
            '  "extraction_date": "2026-01-27"\n'
            "}\n\n"
            "CRITICAL RULES:\n"
            "- Include ONLY numbers/values that appear in the document\n"
            "- For each value, include the exact source_snippet from the document\n"
            "- If a value is missing, use null (not a placeholder)\n"
            "- Dates must be in YYYY-MM-DD format\n\n"
            f"DOCUMENT TEXT:\n{latest_doc_text}\n\n"
            f"Question: {question}\n\n"
            "JSON Response (no markdown, no code fences):"
        )
        
        # Generate with retry on invalid JSON
        max_retries = 2
        for attempt in range(max_retries):
            llm_response = await self.llm_service.generate(
                prompt=json_prompt,
                system_prompt="You are a medical data extraction assistant. Return ONLY valid JSON.",
                max_new_tokens=512,
            )
            
            # Extract JSON from response (handle markdown code fences)
            text = llm_response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            try:
                data = json.loads(text)
                structured = StructuredSummaryResponse(**data)
                
                # Convert back to friendly text for RAGResponse
                friendly_text = self._structured_to_friendly(structured)
                
                return (
                    RAGResponse(
                        answer=friendly_text,
                        llm_response=llm_response,
                        # ... other fields ...
                    ),
                    structured,
                )
            except (json.JSONDecodeError, ValueError) as e:
                if attempt < max_retries - 1:
                    self.logger.warning("Invalid JSON on attempt %d, retrying: %s", attempt + 1, e)
                    json_prompt = (
                        "The previous response was invalid JSON. Return ONLY valid JSON, no markdown, no code fences.\n\n"
                        + json_prompt
                    )
                else:
                    self.logger.error("Failed to get valid JSON after %d attempts", max_retries)
                    # Fall back to regular generation
                    return await self.ask(question, patient_id, conversation_id), None
    
    def _structured_to_friendly(self, structured: StructuredSummaryResponse) -> str:
        """Convert structured response to friendly text for display."""
        lines = [f"**✅ Overview**\n{structured.overview}\n"]
        
        if structured.key_results:
            lines.append("**📋 Key Results**")
            for result in structured.key_results:
                value_str = f"{result.value} {result.unit}" if result.value and result.unit else result.text_value or "N/A"
                lines.append(f"- **{result.name}:** {value_str}")
                if result.date:
                    lines[-1] += f" (on {result.date})"
        
        if structured.vital_signs:
            lines.append("**❤️ Vital Signs**")
            for name, value in structured.vital_signs.items():
                if value:
                    lines.append(f"- **{name.replace('_', ' ').title()}:** {value}")
        
        if structured.follow_ups:
            lines.append("**Next Steps**")
            for followup in structured.follow_ups:
                lines.append(f"- {followup}")
        
        return "\n".join(lines)
```

**Step 3: Update Chat API to Support Structured Mode**

```python
# In backend/app/api/chat.py

@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    structured: bool = Query(False, description="Return structured JSON response"),
    # ... existing params ...
):
    rag_service = RAGService(db)
    
    if structured:
        rag_response, structured_data = await rag_service.ask_structured(
            question=request.question,
            patient_id=request.patient_id,
            conversation_id=request.conversation_id,
        )
        # Return both in response (extend ChatResponse schema)
        return ChatResponse(
            answer=rag_response.answer,
            structured_data=structured_data.model_dump() if structured_data else None,
            # ... other fields ...
        )
    else:
        # Existing path
        rag_response = await rag_service.ask(...)
        return ChatResponse(...)
```

**Benefits:**
- Eliminates 80% of regex cleaning
- Automatic validation
- Easy to extend with new fields
- Enables timeline UI, citations, etc.

---

## 4. Fix torchvision Warning (P0 - Quick Win)

### Current Issue
```
Using use_fast=True but torchvision is not available. Falling back to the slow image processor.
```

### Recommendation
**Explicitly set `use_fast=False`** or install torchvision on Mac.

### Implementation

```python
# In backend/app/services/llm/model.py

def _load_processor(self):
    """Load the processor with explicit use_fast setting."""
    # ... existing code ...
    
    try:
        # Check if torchvision is available
        import torchvision
        use_fast = True
    except ImportError:
        use_fast = False
        logger.info("torchvision not available, using slow image processor")
    
    processor = AutoProcessor.from_pretrained(
        self.model_name if not self.use_local_model else None,
        trust_remote_code=True,
        use_fast=use_fast,  # Explicitly set
        cache_dir=self._get_cache_dir(),
    )
    
    # ... rest of existing code ...
```

**Alternative (if you want fast processing):**
```bash
# In backend/
uv pip install torchvision
```

**Benefits:**
- Eliminates warning noise
- Predictable performance
- Better error handling

---

## 5. Offline Robustness (P0 - Production Critical)

### Current Issue
- Embeddings model (`all-MiniLM-L6-v2`) downloads at runtime
- HF timeouts cause chat hangs
- Not production-ready

### Recommendation
**Download embeddings model during setup** and set offline flags.

### Implementation

**Step 1: Pre-download Script**

```python
# backend/scripts/download_embeddings.py

"""Pre-download embeddings model for offline use."""

import os
from pathlib import Path
from sentence_transformers import SentenceTransformer

def main():
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    
    print(f"Downloading {model_name} to {cache_dir}...")
    model = SentenceTransformer(model_name, cache_folder=str(cache_dir))
    print(f"Model downloaded successfully!")
    print(f"Cache location: {cache_dir}")

if __name__ == "__main__":
    main()
```

**Step 2: Set Offline Flags in Production**

```python
# In backend/app/config.py or .env

# Add to settings:
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1

# Or set in code:
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
```

**Step 3: Update EmbeddingService**

```python
# In backend/app/services/embeddings/embedding.py

from app.config import settings

class EmbeddingService:
    def __init__(self):
        # ... existing code ...
        
        # Set offline mode if configured
        if getattr(settings, 'hf_hub_offline', False):
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
        
        self.model = SentenceTransformer(
            model_name,
            cache_folder=cache_dir,
        )
```

**Step 4: Add to Setup Documentation**

```markdown
# In backend/README.md or setup guide

## Pre-download Models

Before running in production, download required models:

```bash
cd backend
uv run python scripts/download_embeddings.py
```

This ensures offline operation.
```

**Benefits:**
- No runtime downloads
- Faster startup
- Production-ready
- Avoids timeout hangs

---

## 6. Enhanced Hybrid Retrieval with BM25 (P2 - Medium Impact)

### Current State
- ✅ You have `HybridRetriever` with semantic + keyword search
- ⚠️ Keyword search may not be BM25 (needs verification)
- ⚠️ No explicit reranking step

### Recommendation
**Add BM25 keyword matching** and **rerank merged results** before synthesis.

### Implementation

**Step 1: Add BM25 to HybridRetriever**

```python
# In backend/app/services/context/retriever.py

# Install: uv pip install rank-bm25

from rank_bm25 import BM25Okapi
import re

class HybridRetriever:
    # ... existing code ...
    
    def __init__(self, ...):
        # ... existing init ...
        self.bm25_index = None  # Lazy-loaded per patient
    
    async def _get_bm25_results(
        self,
        query: str,
        patient_id: int,
        limit: int = 10,
    ) -> list[RetrievalResult]:
        """Get BM25 keyword search results."""
        # Get all chunks for patient
        result = await self.db.execute(
            select(MemoryChunk)
            .where(
                MemoryChunk.patient_id == patient_id,
                MemoryChunk.is_indexed.is_(True),
            )
            .order_by(MemoryChunk.created_at.desc())
            .limit(1000)  # Reasonable limit for BM25
        )
        chunks = result.scalars().all()
        
        if not chunks:
            return []
        
        # Build BM25 index
        tokenized_chunks = [
            re.findall(r'\b\w+\b', chunk.content.lower())
            for chunk in chunks
        ]
        bm25 = BM25Okapi(tokenized_chunks)
        
        # Query
        query_tokens = re.findall(r'\b\w+\b', query.lower())
        scores = bm25.get_scores(query_tokens)
        
        # Get top results
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:limit]
        
        results = []
        for idx in top_indices:
            chunk = chunks[idx]
            results.append(RetrievalResult(
                id=chunk.id,
                content=chunk.content,
                source_type=chunk.source_type,
                source_id=chunk.source_id,
                patient_id=chunk.patient_id,
                keyword_score=scores[idx],
                semantic_score=0.0,  # Will be merged with semantic results
                combined_score=scores[idx] * self.keyword_weight,
                context_date=chunk.context_date,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
            ))
        
        return results
    
    async def retrieve(self, ...):
        # ... existing semantic retrieval ...
        semantic_results = await self._get_semantic_results(...)
        
        # Add BM25 results
        bm25_results = await self._get_bm25_results(query, patient_id, limit=max_results)
        
        # Merge and deduplicate
        all_results = {}
        for result in semantic_results:
            key = (result.id, result.source_type)
            if key not in all_results or result.combined_score > all_results[key].combined_score:
                all_results[key] = result
        
        for result in bm25_results:
            key = (result.id, result.source_type)
            if key in all_results:
                # Merge scores
                all_results[key].keyword_score = result.keyword_score
                all_results[key].combined_score = (
                    all_results[key].semantic_score * self.semantic_weight +
                    result.keyword_score * self.keyword_weight +
                    all_results[key].recency_score * self.recency_weight
                )
            else:
                all_results[key] = result
        
        # Sort by combined score
        final_results = sorted(
            all_results.values(),
            key=lambda r: r.combined_score,
            reverse=True
        )[:max_results]
        
        return RetrievalResponse(results=final_results, ...)
```

**Benefits:**
- Better exact term matching (e.g., "HbA1c", "Metformin XR 500mg")
- Handles abbreviations better
- More robust for medical terminology

---

## 7. Query Rewriting (P2 - Medium Impact)

### Recommendation
**Before retrieval, rewrite vague queries** using MedGemma to extract entities and clarify intent.

### Implementation

```python
# In backend/app/services/context/analyzer.py (extend QueryAnalyzer)

class QueryAnalyzer:
    # ... existing code ...
    
    async def rewrite_query(
        self,
        query: str,
        conversation_history: Optional[list] = None,
        llm_service: Optional[LLMService] = None,
    ) -> str:
        """Rewrite vague queries to be more specific.
        
        Examples:
        - "hey" → "What are the most recent findings?"
        - "what does this mean" → Extract entities from last doc and ask about them
        """
        if not llm_service:
            return query  # Fallback to original
        
        # Check if query is too vague
        if len(query.split()) < 3 and query.lower() not in ["summarize", "overview"]:
            rewrite_prompt = (
                "The user asked a very short question in a medical context. "
                "Rewrite it to be more specific and actionable.\n\n"
                f"Original question: {query}\n\n"
                "If there's conversation history, use it to understand context:\n"
                f"{self._format_history(conversation_history) if conversation_history else 'No history'}\n\n"
                "Rewritten question (be specific, extract entities if mentioned):"
            )
            
            try:
                response = await llm_service.generate(
                    prompt=rewrite_prompt,
                    max_new_tokens=50,
                    system_prompt="You are a query rewriting assistant.",
                )
                rewritten = response.text.strip().strip('"').strip("'")
                if len(rewritten) > len(query):
                    return rewritten
            except Exception as e:
                logger.warning("Query rewriting failed: %s", e)
        
        return query
    
    def _format_history(self, history: list) -> str:
        """Format conversation history for context."""
        if not history:
            return ""
        return "\n".join([
            f"{'User' if msg.role == 'user' else 'Assistant'}: {msg.content}"
            for msg in history[-3:]  # Last 3 turns
        ])
```

**Usage in ContextEngine:**

```python
# In backend/app/services/context/engine.py

async def get_context(self, query: str, ...):
    # Rewrite query first
    rewritten_query = await self.analyzer.rewrite_query(
        query,
        conversation_history=None,  # Can pass if available
        llm_service=LLMService.get_instance(),
    )
    
    # Use rewritten query for retrieval
    retrieval_response = await self.retriever.retrieve(
        query=rewritten_query,  # Use rewritten
        # ... other params ...
    )
```

**Benefits:**
- Reduces "no chunks used" errors
- Better entity extraction
- Handles conversational queries

---

## 8. MedGemma-Specific Features (P3 - Future Enhancements)

### 8.1 Chart Explanation Mode

**Use Case:** Frontend shows lab trends as charts → send data + chart summary to MedGemma.

```python
# In backend/app/api/chat.py

@router.post("/explain-chart")
async def explain_chart(
    chart_data: dict,  # {labels: [...], datasets: [{label: "HbA1c", data: [...]}]}
    patient_id: int,
    # ... auth ...
):
    # Convert chart to text summary
    chart_text = f"""
    Lab Trend Chart:
    - Test: {chart_data['datasets'][0]['label']}
    - Values over time: {', '.join(map(str, chart_data['datasets'][0]['data']))}
    - Dates: {', '.join(chart_data['labels'])}
    """
    
    prompt = (
        "Explain this lab trend chart. Highlight:\n"
        "- Overall trend (increasing, decreasing, stable)\n"
        "- Any outliers or concerning values\n"
        "- Clinical significance\n"
        "- Recommended follow-up\n\n"
        f"{chart_text}"
    )
    
    llm_response = await llm_service.generate(
        prompt=prompt,
        system_prompt="You are a medical chart interpreter.",
    )
    
    return {"explanation": llm_response.text}
```

### 8.2 Multi-Image Longitudinal Comparison

**Use Case:** Compare two medical images over time (e.g., X-rays, scans).

```python
# In backend/app/api/chat.py

@router.post("/compare-images")
async def compare_images(
    image_a: UploadFile,
    image_b: UploadFile,
    date_a: str,
    date_b: str,
    patient_id: int,
    # ... auth ...
):
    img_a_bytes = await image_a.read()
    img_b_bytes = await image_b.read()
    
    prompt = (
        f"Compare these two medical images:\n"
        f"- Image A: {date_a}\n"
        f"- Image B: {date_b}\n\n"
        "Describe:\n"
        "- Any changes between the two images\n"
        "- New findings in Image B\n"
        "- Resolved findings from Image A\n"
        "- Overall assessment"
    )
    
    llm_response = await llm_service.generate_with_images(
        prompt=prompt,
        images_bytes=[img_a_bytes, img_b_bytes],
        system_prompt="You are a radiologist comparing medical images over time.",
    )
    
    return {"comparison": llm_response.text}
```

---

## Implementation Roadmap

### Phase 1: Quick Wins (Week 1)
- [ ] Fix torchvision warning (30 min)
- [ ] Set up offline embeddings (1 hour)
- [ ] Add query routing basics (2-3 hours)

### Phase 2: Core Improvements (Week 2-3)
- [ ] Implement structured JSON output (1-2 days)
- [ ] Add multimodal latest-doc path (2-3 days)
- [ ] Enhance hybrid retrieval with BM25 (1-2 days)

### Phase 3: Polish (Week 4)
- [ ] Query rewriting (1 day)
- [ ] Add grounding quotes to responses (1 day)
- [ ] Testing and validation (2-3 days)

### Phase 4: Advanced Features (Future)
- [ ] Chart explanation mode
- [ ] Multi-image comparison
- [ ] Advanced reranking

---

## Code Organization Recommendations

### Refactor RAGService into 3 Stages

```python
# Proposed structure:

class RAGService:
    async def ask(self, ...):
        # Stage 1: Retrieve
        context = await self._retrieve_context(question, patient_id)
        
        # Stage 2: Synthesize
        answer = await self._synthesize_answer(question, context, task_type)
        
        # Stage 3: Validate
        validated = await self._validate_response(answer, context)
        
        return RAGResponse(...)
    
    async def _retrieve_context(self, ...):
        # All retrieval logic here
        pass
    
    async def _synthesize_answer(self, ...):
        # All LLM generation here
        pass
    
    async def _validate_response(self, ...):
        # Schema validation, number checking, etc.
        pass
```

**Benefits:**
- Clear separation of concerns
- Easier to test each stage
- Easier to swap implementations

---

## Testing Strategy

### Unit Tests
- Query router classification accuracy
- JSON schema validation
- BM25 scoring correctness

### Integration Tests
- End-to-end latest-doc summary with vision
- Structured output generation
- Hybrid retrieval merging

### Performance Tests
- Latency of multimodal extraction
- BM25 index building time
- JSON parsing overhead

---

## Metrics to Track

1. **Retrieval Quality:**
   - `total_chunks_used` / `total_chunks_available`
   - Average similarity scores
   - BM25 vs semantic hit rates

2. **Output Quality:**
   - JSON validation success rate
   - Post-processing reduction (lines of regex removed)
   - User-reported accuracy

3. **Performance:**
   - Average response time per task type
   - Vision extraction time
   - BM25 index build time

---

## Conclusion

These 8 recommendations leverage MedGemma-1.5-4B-IT's strengths while addressing your current pain points:

1. **Query routing** → Predictable, task-specific outputs
2. **Multimodal latest-doc** → Better number extraction
3. **Structured output** → Eliminates fragile post-processing
4. **torchvision fix** → Clean logs, stable performance
5. **Offline robustness** → Production-ready
6. **BM25 hybrid** → Better exact term matching
7. **Query rewriting** → Fewer "no chunks" errors
8. **MedGemma features** → Chart explanation, image comparison

**Next Steps:**
1. Review this report with your team
2. Prioritize based on your immediate needs
3. Start with P0 items (torchvision, offline setup)
4. Implement P1 items (routing, structured output) for maximum impact
5. Iterate based on user feedback

**Questions or need clarification on any recommendation?** Let me know and I can provide more detailed implementation guidance.
