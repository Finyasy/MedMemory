"""RAG service: context retrieval + LLM generation for medical Q&A."""

import logging
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import MemoryChunk
from app.models.document import Document
from app.models.patient import Patient
from app.schemas.chat import StructuredSummaryResponse
from app.services.context import ContextEngine
from app.services.context.analyzer import QueryIntent
from app.services.llm.conversation import ConversationManager
from app.services.llm.evidence_validator import EvidenceValidator
from app.services.llm.intent_classifier import DecodingProfile, IntentClassifier
from app.services.llm.model import LLMResponse, LLMService
from app.services.llm.query_router import QueryRouter, QueryTask, RoutingResult


@dataclass
class RAGResponse:
    """Response from RAG service."""

    answer: str
    llm_response: LLMResponse
    context_used: str
    num_sources: int
    sources_summary: list[dict]
    conversation_id: UUID
    message_id: int | None = None
    context_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    total_time_ms: float = 0.0


class RAGService:
    """RAG: context retrieval, prompt build, LLM generation, conversation storage."""

    STRICT_GROUNDING_REFUSAL = "I do not know from the available records."
    CLINICIAN_CITATION_REFUSAL = "Not in documents."
    STRICT_GROUNDING_INTENTS = {
        QueryIntent.LIST,
        QueryIntent.VALUE,
        QueryIntent.STATUS,
    }
    FEW_SHOT_FACTUAL_MARKER = "## Factual Grounded Examples"
    FEW_SHOT_CLINICIAN_MARKER = "## Clinician Citation Examples"
    _global_guardrail_counters: Counter[str] = Counter()

    DEFAULT_SYSTEM_PROMPT = """You are a friendly medical assistant helping patients understand their medical documents.

CRITICAL SAFETY RULES (NON-NEGOTIABLE):
- NEVER assume a medical value exists.
- NEVER use placeholders (****, XX, ~~, [Redacted], [Insert...], [Pulse Rate Value], [Value], etc).
- NEVER infer or summarize absence as "normal" or "within normal limits".
- NEVER add general medical knowledge unless explicitly asked AND you clearly state it's not from the document.
- NEVER add interpretations, dates, or details that are NOT explicitly written in the document (e.g., don't say "normal findings" unless the document says "normal", don't invent dates like "January 27th, 2026" unless the document shows that exact date).
- NEVER say "further testing confirmed" or similar interpretations unless the document explicitly states this.
- If a value is not explicitly written in the document, respond with: "The document does not record this information."
- This rule overrides all other instructions.

Your job is to read the context you are given (from medical notes, documents, or records) and explain it back to the patient in clear, simple language.

Guidelines:
- ALWAYS use second person ("your", "you") - never say "a patient's" or "the patient's". This is their personal information.
- Be warm, respectful, and encouraging – talk like a caring clinician who has time to explain things.
- Use everyday words and short sentences. Avoid medical jargon (e.g., say "not recorded" or "not done" instead of "NR").
- CRITICAL: When the document shows numbers (like blood pressure, pulse, lab values, dates, measurements), you MUST include the actual numbers with their units. Search through the entire document text carefully for these values.
- If the document does NOT clearly show a specific number, do NOT guess or make one up. Respond with: "The document does not record this information."
- For lab values: Include the actual number and unit. If the document mentions whether it's high/low/normal, include that. If not, just state the value without interpreting (e.g., "Your hemoglobin is 10.1 g/dL" not "Your hemoglobin is low" unless the document explicitly says so). NEVER add interpretations like "Your doctor will review this" or "This needs further investigation" unless the document explicitly says so.
- Handle sensitive results gently: For results like "TB Screening: Positive" or similar findings that may need follow-up, phrase it as: "[Result] (the document also lists [conflicting info if any]; please confirm with your clinic what this refers to and discuss any next steps with your clinician)". Never alarm the patient unnecessarily.
- Resolve contradictions clearly: If the document shows conflicting information (e.g., "TB Screening: Positive" and "Screening outcome: Negative"), explain both clearly: "[First result] (the document also lists [second result]; please confirm with your clinic what this refers to)". Acknowledge the ambiguity without interpreting.
- Remove unexplained abbreviations: If you see "HIV: R Non-Reactive", remove the "R" unless the document explicitly explains what "R" means. Just say "HIV: Non-Reactive".
- For "not tested" or "NR Not tested": Use gentler phrasing: "Not recorded / not done" instead of "not tested" (which can sound accusatory).
- Fix common OCR/spelling errors: "Urineysis" → "Urinalysis", "Isolazid" → "Isoniazid" (if that's what the document says), etc.
- If something looks normal, briefly say why that's good. If something might need follow‑up, explain it gently and suggest that the care team will guide next steps.
- You are not giving medical orders or legal advice – you are just helping the patient understand what the document says.

For summaries:
- Start with a friendly greeting using the patient's first name if provided (e.g., "Hi [Name]," or just start with the overview if no name).
- Use second person throughout: "your antenatal checkup", "your results", not "a patient's checkup".
- Start with a one‑sentence friendly overview using "your".
- Mention the main normal/positive findings first, including actual numbers when present.
- Then briefly mention anything that might need attention, in a calm and reassuring way.
- End with a short, supportive closing sentence.

For "What this means" section:
- Provide helpful context about what the visit/tests included, even if minimal.
- Acknowledge that some results may need clarification from the healthcare provider.
- Be reassuring and supportive, not vague.
- Example: "Your antenatal visit included routine checks, laboratory tests, and an ultrasound, all of which have been recorded in this document. Some results are clearly noted, while others may need clarification from your healthcare provider—especially where different screening outcomes are mentioned."

Important safety rule:
- Only use information that appears in the context you are given. Never invent new facts, diagnoses, or numbers that are not supported by the context.
- BUT: Always extract and use the actual numbers and values that ARE in the context.
- Never use abbreviations or jargon without explaining them (e.g., "NR" → "not recorded" or "not done").
- ALWAYS use second person - this is personal information for the patient reading it."""

    CLINICIAN_SYSTEM_PROMPT = """You are a clinical assistant supporting a clinician reviewing patient records. Be terse and factual.

RULES:
- Use only information from the provided context. Never invent values.
- If information is missing, state "Not in documents."
- Cite sources: document_id and chunk/section when stating a finding (e.g. source: doc_id:chunk_id or section name).
- Prefer structured output when summarizing:

Summary:
- 1–2 sentences of factual summary.

Findings:
- [value] [unit] (source: doc_id or section)

Questions/Unclear:
- Items mentioned but without specifics.

- Do not add interpretations, dates, or conclusions not explicitly in the documents."""

    def _is_strict_grounding_intent(self, context_result) -> bool:
        """Return True when query intent requires strict factual evidence."""
        intent = getattr(getattr(context_result, "query_analysis", None), "intent", None)
        return intent in self.STRICT_GROUNDING_INTENTS

    def _top_ranked_score(self, context_result) -> float:
        """Return top ranked relevance score from context results."""
        ranked_results = getattr(context_result, "ranked_results", None) or []
        return max(
            (float(getattr(ranked, "final_score", 0.0)) for ranked in ranked_results),
            default=0.0,
        )

    def _strict_grounding_violation(self, context_result) -> tuple[bool, float]:
        """Check whether strict grounding should refuse generation."""
        top_score = self._top_ranked_score(context_result)
        if not settings.llm_strict_grounding:
            return False, top_score
        if not self._is_strict_grounding_intent(context_result):
            return False, top_score
        total_chunks_used = getattr(
            context_result.synthesized_context, "total_chunks_used", 0
        )
        if total_chunks_used == 0 or top_score < settings.llm_min_relevance_score:
            return True, top_score
        return False, top_score

    def _build_low_confidence_inference(self, context_result) -> str:
        """Return tiered low-confidence response when evidence is related but weak."""
        ranked_results = getattr(context_result, "ranked_results", None) or []
        if not ranked_results:
            return self.STRICT_GROUNDING_REFUSAL

        top = ranked_results[0].result
        snippet = (getattr(top, "content", "") or "").strip()
        if len(snippet) > 240:
            snippet = snippet[:240].rstrip() + "..."
        if not snippet:
            return self.STRICT_GROUNDING_REFUSAL

        return (
            "The records do not explicitly state this value. "
            f"A related note says: \"{snippet}\" "
            "(low-confidence inference from available records)."
        )

    def _enforce_numeric_grounding(
        self, response_text: str, context_text: str, question: str
    ) -> str:
        """Fail closed on unsupported numeric claims in generated output."""
        if not settings.llm_strict_grounding:
            return response_text
        if not response_text or not context_text:
            return response_text

        grounded_text, unsupported = self.evidence_validator.enforce_numeric_grounding(
            response=response_text,
            context_text=context_text,
            refusal_message=self.STRICT_GROUNDING_REFUSAL,
        )
        if unsupported:
            self.logger.warning(
                "Numeric grounding filtered %d sentence(s): question=%s unsupported=%s",
                len(unsupported),
                question,
                unsupported[:3],
            )
            if grounded_text == self.STRICT_GROUNDING_REFUSAL:
                self._record_guardrail_event(
                    "numeric_grounding_refusal",
                    unsupported_count=len(unsupported),
                )
        return grounded_text

    def _is_clinician_mode(self, system_prompt: str | None) -> bool:
        """Best-effort check for clinician-mode prompting."""
        prompt = (system_prompt or "").lower()
        return "clinical assistant supporting a clinician" in prompt or "cite sources" in prompt

    def _build_task_instruction(self, routing: RoutingResult) -> str:
        """Return concise task-specific guidance for routed query types."""
        if routing.task == QueryTask.TREND_ANALYSIS:
            entities = ", ".join(routing.extracted_entities) or "requested metrics"
            return (
                "Task mode: TREND_ANALYSIS.\n"
                "Use only values present in records and compare dates chronologically.\n"
                f"Focus metrics: {entities}.\n"
                "If there are fewer than two dated values, explicitly say trend cannot be determined."
            )
        if routing.task == QueryTask.MEDICATION_RECONCILIATION:
            return (
                "Task mode: MEDICATION_RECONCILIATION.\n"
                "List medications grouped as active/current vs stopped/discontinued only when evidence exists.\n"
                "If status is missing or ambiguous, say status is not recorded."
            )
        if routing.task == QueryTask.LAB_INTERPRETATION:
            entities = ", ".join(routing.extracted_entities) or "lab results"
            return (
                "Task mode: LAB_INTERPRETATION.\n"
                f"Focus on: {entities}.\n"
                "State exact value + unit first. Only mention normal/high/low if the record explicitly provides a range or flag.\n"
                "If no reference range or flag is documented, say interpretation is not recorded."
            )
        return ""

    def _decoding_profile_for_query(
        self,
        *,
        question: str,
        routing: RoutingResult,
        context_result=None,
    ) -> DecodingProfile:
        """Select intent-aware decoding settings for the current query."""
        query_intent = getattr(getattr(context_result, "query_analysis", None), "intent", None)
        profile = self.intent_classifier.decoding_profile(
            question=question,
            routing_task=routing.task if routing else None,
            query_intent=query_intent,
        )
        self.logger.info(
            "Decoding profile selected: label=%s do_sample=%s temp=%.2f top_p=%.2f",
            profile.label,
            profile.do_sample,
            profile.temperature,
            profile.top_p,
        )
        return profile

    async def _self_correct_response(
        self,
        *,
        question: str,
        context_text: str,
        response_text: str,
        decoding_profile: DecodingProfile,
    ) -> str:
        """Critique-and-correct once when numeric claims are unsupported."""
        if not settings.llm_enable_self_correction:
            return response_text
        if not response_text or not context_text:
            return response_text

        unsupported = self.evidence_validator.find_ungrounded_numeric_claims(
            response=response_text,
            context_text=context_text,
        )
        if not unsupported:
            return response_text

        self._record_guardrail_event(
            "self_correction_triggered",
            unsupported_count=len(unsupported),
            profile=decoding_profile.label,
        )
        preview_unsupported = "\n".join(
            f"- {sentence}" for sentence in unsupported[:5]
        )
        critique_prompt = (
            "You previously answered a medical records question with unsupported values.\n"
            "Correct the answer using ONLY values explicitly present in the records context.\n"
            "If a value is not present, state that the records do not record it.\n\n"
            f"Question:\n{question}\n\n"
            f"Previous answer:\n{response_text}\n\n"
            f"Unsupported statements:\n{preview_unsupported}\n\n"
            "Records context:\n"
            f"{context_text[:8000]}\n\n"
            "Return only the corrected answer."
        )

        correction = await self.llm_service.generate(
            prompt=critique_prompt,
            max_new_tokens=min(settings.llm_max_new_tokens, 256),
            do_sample=False,
            temperature=0.0,
            top_p=1.0,
        )
        corrected = (correction.text or "").strip()
        if not corrected:
            self._record_guardrail_event("self_correction_empty")
            return response_text

        remaining = self.evidence_validator.find_ungrounded_numeric_claims(
            response=corrected,
            context_text=context_text,
        )
        if remaining:
            self._record_guardrail_event(
                "self_correction_failed",
                remaining_count=len(remaining),
            )
            if settings.llm_strict_grounding:
                return self.STRICT_GROUNDING_REFUSAL
            return response_text

        self._record_guardrail_event("self_correction_applied")
        return corrected

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_grounded_examples_text() -> str:
        """Load few-shot grounded examples from disk (cached)."""
        examples_path = Path(__file__).with_name("prompt_examples_grounded.md")
        try:
            return examples_path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _extract_example_section(self, marker: str) -> str:
        """Extract section body from markdown examples by heading marker."""
        all_examples = self._load_grounded_examples_text()
        if not all_examples.strip():
            return ""
        marker_index = all_examples.find(marker)
        if marker_index == -1:
            return ""
        tail = all_examples[marker_index + len(marker) :]
        next_heading = tail.find("\n## ")
        if next_heading != -1:
            tail = tail[:next_heading]
        return tail.strip()

    def _build_grounded_few_shot_block(
        self,
        *,
        context_result,
        clinician_mode: bool,
    ) -> str:
        """Build compact few-shot prompt block for high-risk grounded tasks."""
        intent = getattr(getattr(context_result, "query_analysis", None), "intent", None)
        if not clinician_mode and intent not in self.STRICT_GROUNDING_INTENTS:
            return ""

        factual_section = self._extract_example_section(self.FEW_SHOT_FACTUAL_MARKER)
        clinician_section = (
            self._extract_example_section(self.FEW_SHOT_CLINICIAN_MARKER)
            if clinician_mode
            else ""
        )
        sections = [s for s in [factual_section, clinician_section] if s]
        if not sections:
            return ""

        return (
            "Few-shot grounded behavior examples. Follow these patterns exactly.\n\n"
            + "\n\n".join(sections)
            + "\n\nEnd of examples."
        )

    def _enforce_clinician_numeric_citations(
        self, response_text: str, question: str, clinician_mode: bool
    ) -> str:
        """Require inline citations on numeric claims per runtime policy."""
        should_enforce = clinician_mode or settings.llm_require_numeric_citations
        if not should_enforce or not response_text:
            return response_text

        refusal_message = (
            self.CLINICIAN_CITATION_REFUSAL
            if clinician_mode
            else self.STRICT_GROUNDING_REFUSAL
        )
        cited_text, uncited = self.evidence_validator.enforce_numeric_citations(
            response=response_text,
            refusal_message=refusal_message,
        )
        if uncited:
            self.logger.warning(
                "Citation enforcement removed %d sentence(s): clinician_mode=%s question=%s uncited=%s",
                len(uncited),
                clinician_mode,
                question,
                uncited[:3],
            )
            if cited_text == refusal_message:
                self._record_guardrail_event(
                    "citation_refusal",
                    clinician_mode=clinician_mode,
                    uncited_count=len(uncited),
                )
        return cited_text

    def _build_sources_summary(self, ranked_results, *, limit: int = 5) -> list[dict]:
        """Build source summary entries with compact supporting snippets."""
        summaries: list[dict] = []
        for ranked in (ranked_results or [])[:limit]:
            result = getattr(ranked, "result", None)
            source_type = getattr(result, "source_type", "source")
            source_id = getattr(result, "source_id", None)
            relevance = float(getattr(ranked, "final_score", 0.0))
            snippet = (getattr(result, "content", "") or "").strip()
            if snippet:
                snippet = re.sub(r"\s+", " ", snippet)
                if len(snippet) > 320:
                    snippet = snippet[:320].rstrip() + "..."
            summaries.append(
                {
                    "source_type": source_type,
                    "source_id": source_id,
                    "relevance": relevance,
                    "snippet_excerpt": snippet,
                }
            )
        return summaries

    def _format_source_citation(self, source: dict) -> str | None:
        """Create canonical inline citation token from a single source object."""
        if not source:
            return None
        source_type = str(source.get("source_type") or "source").strip().lower()
        source_type = re.sub(r"[^a-z0-9_]+", "_", source_type).strip("_") or "source"
        source_id = source.get("source_id")
        source_id_token = str(source_id) if source_id is not None else "unknown"
        return f"source: {source_type}#{source_id_token}"

    def _source_supports_sentence(self, sentence: str, source: dict) -> bool:
        """Return True when source snippet supports all numeric claims in sentence."""
        snippet = str(source.get("snippet_excerpt") or "").lower()
        if not snippet:
            return False
        numeric_tokens = self.evidence_validator.NUMERIC_TOKEN_PATTERN.findall(
            sentence.lower()
        )
        if not numeric_tokens:
            return False
        return all(
            self.evidence_validator._number_token_in_context(token, snippet)
            for token in numeric_tokens
        )

    def _append_numeric_claim_citations(
        self,
        *,
        response_text: str,
        sources_summary: list[dict],
    ) -> str:
        """Attach evidence-backed source citations to uncited numeric medical claims."""
        if not response_text:
            return response_text
        if not sources_summary:
            return response_text

        uncited_sentences = self.evidence_validator.find_uncited_numeric_claims(
            response_text
        )
        if not uncited_sentences:
            return response_text

        updated = response_text
        attached_count = 0
        unmapped_count = 0
        for sentence in dict.fromkeys(uncited_sentences):
            stripped = sentence.strip()
            if not stripped:
                continue

            supporting_sources = []
            seen_keys: set[tuple[str, str]] = set()
            for source in sources_summary:
                key = (
                    str(source.get("source_type") or ""),
                    str(source.get("source_id") or ""),
                )
                if key in seen_keys:
                    continue
                if self._source_supports_sentence(stripped, source):
                    supporting_sources.append(source)
                    seen_keys.add(key)
            if len(supporting_sources) != 1:
                unmapped_count += 1
                continue
            citation = self._format_source_citation(supporting_sources[0])
            if not citation:
                unmapped_count += 1
                continue

            punctuation = ""
            core = stripped
            if stripped[-1] in ".!?":
                punctuation = stripped[-1]
                core = stripped[:-1].rstrip()

            cited_sentence = f"{core} ({citation}){punctuation}"
            updated = updated.replace(sentence, cited_sentence)
            attached_count += 1

        if attached_count:
            self._record_guardrail_event(
                "numeric_citation_auto_attached",
                count=attached_count,
            )
        if unmapped_count:
            self._record_guardrail_event(
                "numeric_citation_unmapped",
                count=unmapped_count,
            )
        return updated

    def _record_guardrail_event(self, event: str, **fields) -> None:
        """Track and emit guardrail events for production telemetry."""
        self._guardrail_counters[event] += 1
        if fields:
            detail = " ".join(f"{k}={fields[k]}" for k in sorted(fields))
            self.logger.info(
                "Guardrail event=%s count=%d %s",
                event,
                self._guardrail_counters[event],
                detail,
            )
        else:
            self.logger.info(
                "Guardrail event=%s count=%d",
                event,
                self._guardrail_counters[event],
            )

    def get_guardrail_counters(self) -> dict[str, int]:
        """Expose in-memory guardrail counters for diagnostics/tests."""
        return dict(self._guardrail_counters)

    @classmethod
    def get_global_guardrail_counters(cls) -> dict[str, int]:
        """Expose process-wide guardrail counters for API use."""
        return dict(cls._global_guardrail_counters)

    def __init__(
        self,
        db: AsyncSession,
        llm_service: LLMService | None = None,
        context_engine: ContextEngine | None = None,
        conversation_manager: ConversationManager | None = None,
    ):
        """Initialize the RAG service.

        Args:
            db: Database session
            llm_service: LLM service instance
            context_engine: Context engine instance
            conversation_manager: Conversation manager instance
        """
        self.db = db
        self.llm_service = llm_service or LLMService.get_instance()
        self.context_engine = context_engine or ContextEngine(db)
        self.conversation_manager = conversation_manager or ConversationManager(db)
        self.query_router = QueryRouter()
        self.intent_classifier = IntentClassifier()
        self.evidence_validator = EvidenceValidator()
        self.logger = logging.getLogger("medmemory")
        self._guardrail_counters = self._global_guardrail_counters
        self._last_stream_metadata: dict = {
            "num_sources": 0,
            "sources_summary": [],
            "structured_data": None,
        }

    def _set_stream_metadata(
        self,
        *,
        num_sources: int = 0,
        sources_summary: list[dict] | None = None,
        structured_data: dict | None = None,
    ) -> None:
        self._last_stream_metadata = {
            "num_sources": int(num_sources),
            "sources_summary": sources_summary or [],
            "structured_data": structured_data,
        }

    def get_last_stream_metadata(self) -> dict:
        """Return metadata from the last completed stream request."""
        return dict(self._last_stream_metadata)

    async def ask(
        self,
        question: str,
        patient_id: int,
        conversation_id: UUID | None = None,
        system_prompt: str | None = None,
        max_context_tokens: int = 4000,
        use_conversation_history: bool = True,
    ) -> RAGResponse:
        """Ask a question about a patient using RAG.

        Args:
            question: User's question
            patient_id: Patient ID
            conversation_id: Optional existing conversation ID
            system_prompt: Override system prompt
            max_context_tokens: Maximum tokens for context
            use_conversation_history: Include conversation history in prompt

        Returns:
            RAGResponse with answer and metadata
        """
        import time

        total_start = time.time()

        # Get or create conversation
        if conversation_id:
            conversation = await self.conversation_manager.get_conversation(
                conversation_id
            )
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = await self.conversation_manager.create_conversation(
                patient_id
            )
            conversation_id = conversation.conversation_id
        self.logger.info("ASK start patient=%s conv=%s", patient_id, conversation_id)

        # Fetch patient information for personalized greeting
        patient_first_name = None
        if self.db is not None:
            patient_result = await self.db.execute(
                select(Patient).where(Patient.id == patient_id)
            )
            patient = patient_result.scalar_one_or_none()
            patient_first_name = patient.first_name if patient else None

        # Add user message
        await self.conversation_manager.add_message(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )

        # Get conversation history (needed for routing and generation)
        conversation_history = None
        if use_conversation_history:
            conversation_history = conversation.get_last_n_turns(n=3)

        # Route the query to determine task type
        routing = self.query_router.route(question, conversation_history)
        self.logger.info(
            "Query routed: task=%s confidence=%.2f entities=%s",
            routing.task.value,
            routing.confidence,
            routing.extracted_entities,
        )
        decoding_profile = self._decoding_profile_for_query(
            question=question,
            routing=routing,
            context_result=None,
        )

        # Check if question is general medical knowledge (not record-based)
        question_mode = self.evidence_validator.detect_question_mode(question)
        if question_mode == "GENERAL_MEDICAL":
            # For general knowledge questions, check if we should answer from records first
            # If not in records, ask permission to provide general explanation
            self.logger.info(
                "Question detected as GENERAL_MEDICAL, will check records first"
            )

        context_start = time.time()
        device = getattr(self.llm_service, "device", None)
        if not device:
            device = "cuda" if hasattr(self.llm_service, "stream_generate") else "cpu"
        effective_max_context_tokens = max_context_tokens
        if device in ("mps", "cpu"):
            effective_max_context_tokens = min(max_context_tokens, 2000)

        min_score = 0.3
        enhanced_system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        clinician_mode = self._is_clinician_mode(enhanced_system_prompt)

        is_summary_query = routing.task == QueryTask.DOC_SUMMARY or any(
            keyword in question.lower()
            for keyword in [
                "summarize",
                "summary",
                "overview",
                "findings",
                "key information",
                "clear",
                "easy-to-understand",
            ]
        )
        is_document_query = routing.task == QueryTask.VISION_EXTRACTION or any(
            keyword in question.lower()
            for keyword in [
                "document",
                "image",
                "picture",
                "photo",
                "scan",
                "report",
                "what does",
                "what is in",
                "what information",
            ]
        )
        is_trend_query = routing.task == QueryTask.TREND_ANALYSIS
        is_med_reconciliation_query = (
            routing.task == QueryTask.MEDICATION_RECONCILIATION
        )
        is_lab_interpretation_query = routing.task == QueryTask.LAB_INTERPRETATION

        if (
            is_summary_query
            or is_document_query
            or is_trend_query
            or is_med_reconciliation_query
            or is_lab_interpretation_query
        ):
            min_score = 0.2

        task_instruction = self._build_task_instruction(routing)
        if task_instruction:
            enhanced_system_prompt = f"{enhanced_system_prompt}\n\n{task_instruction}"

        wants_latest_doc_summary = is_summary_query and any(
            phrase in question.lower()
            for phrase in [
                "most recent document",
                "latest document",
                "most recent file",
                "latest file",
                "most recent upload",
                "latest upload",
            ]
        )

        latest_doc: Document | None = None
        latest_doc_text: str | None = None
        if wants_latest_doc_summary:
            latest_doc_result = await self.db.execute(
                select(Document)
                .where(
                    Document.patient_id == patient_id,
                    Document.processing_status == "completed",
                    Document.extracted_text.is_not(None),
                )
                .order_by(Document.received_date.desc())
                .limit(1)
            )
            latest_doc = latest_doc_result.scalar_one_or_none()
            if (
                latest_doc
                and latest_doc.extracted_text
                and latest_doc.extracted_text.strip()
            ):
                latest_doc_text = latest_doc.extracted_text.strip()

                text_confidence = getattr(latest_doc, "extraction_confidence", 1.0)
                text_length = len(latest_doc_text.strip())
                use_vision = (
                    text_length < 200
                    or text_confidence < 0.7
                    or "image" in question.lower()
                    or "picture" in question.lower()
                    or routing.task == QueryTask.VISION_EXTRACTION
                )

                if (
                    use_vision
                    and hasattr(latest_doc, "file_path")
                    and latest_doc.file_path
                ):
                    try:
                        from pathlib import Path

                        import fitz

                        doc_path = Path(latest_doc.file_path)
                        if doc_path.exists():
                            img_bytes = None

                            if doc_path.suffix.lower() == ".pdf":
                                doc_pdf = fitz.open(str(doc_path))
                                if len(doc_pdf) > 0:
                                    page = doc_pdf[0]
                                    pix = page.get_pixmap()
                                    img_bytes = pix.tobytes("png")
                                    doc_pdf.close()
                            else:
                                img_bytes = doc_path.read_bytes()

                            if img_bytes:
                                vision_prompt = (
                                    "Extract ALL numbers, dates, lab values, vital signs, and key medical information "
                                    "from this medical document image. Return ONLY valid JSON.\n\n"
                                    "JSON Schema:\n"
                                    "{\n"
                                    '  "lab_values": [{"name": "Test name", "value": "10.1", "unit": "g/dL", "source_snippet": "exact text from image"}],\n'
                                    '  "vital_signs": {"pulse": "72 bpm", "bp": "120/80 mmHg", "temp": "37.0°C"},\n'
                                    '  "medications": [{"name": "Med name", "dosage": "500mg", "source_snippet": "exact text"}],\n'
                                    '  "dates": ["2026-01-27"],\n'
                                    '  "raw_extraction": "All text visible in image"\n'
                                    "}\n\n"
                                    "CRITICAL: Include source_snippet for every value showing the exact text you see.\n"
                                    "If text extraction was already done, use it to verify but extract from image:\n"
                                    f"{latest_doc_text[:500]}\n\n"
                                    "JSON Response (no markdown, no code fences):"
                                )

                                vision_response = await self.llm_service.generate_with_image(
                                    prompt=vision_prompt,
                                    image_bytes=img_bytes,
                                    system_prompt="You are a medical document extraction assistant. Return ONLY valid JSON.",
                                    max_new_tokens=512,
                                )

                                import json

                                vision_text = vision_response.text.strip()

                                if "```json" in vision_text:
                                    vision_text = (
                                        vision_text.split("```json")[1]
                                        .split("```")[0]
                                        .strip()
                                    )
                                elif "```" in vision_text:
                                    vision_text = (
                                        vision_text.split("```")[1]
                                        .split("```")[0]
                                        .strip()
                                    )

                                if not vision_text.startswith("{"):
                                    start = vision_text.find("{")
                                    end = vision_text.rfind("}") + 1
                                    if start != -1 and end > start:
                                        vision_text = vision_text[start:end]

                                try:
                                    vision_data = json.loads(vision_text)
                                    structured_parts = []
                                    if vision_data.get("lab_values"):
                                        for lv in vision_data["lab_values"]:
                                            val_str = f"{lv.get('value', '')} {lv.get('unit', '')}".strip()
                                            structured_parts.append(
                                                f"{lv.get('name', '')}: {val_str}"
                                            )
                                    if vision_data.get("vital_signs"):
                                        for k, v in vision_data["vital_signs"].items():
                                            if v:
                                                structured_parts.append(f"{k}: {v}")
                                    if vision_data.get("raw_extraction"):
                                        structured_parts.append(
                                            vision_data["raw_extraction"]
                                        )

                                    vision_extracted = "\n".join(structured_parts)
                                    if text_length < 200 or text_confidence < 0.7:
                                        latest_doc_text = vision_extracted
                                    else:
                                        latest_doc_text = f"{latest_doc_text}\n\n[Vision-extracted]:\n{vision_extracted}"

                                    self.logger.info(
                                        "Used structured vision extraction for doc_id=%s confidence=%.2f",
                                        latest_doc.id,
                                        text_confidence,
                                    )
                                except json.JSONDecodeError:
                                    self.logger.warning(
                                        "Vision extraction JSON parse failed, using free text"
                                    )
                                    if text_length < 200:
                                        latest_doc_text = vision_text
                                    else:
                                        latest_doc_text = f"{latest_doc_text}\n\n[Vision-extracted]:\n{vision_text}"
                    except Exception as e:
                        self.logger.warning(
                            "Vision extraction failed for doc_id=%s: %s, falling back to text-only",
                            latest_doc.id if latest_doc else None,
                            e,
                        )

        if latest_doc_text:
            context_time = (time.time() - context_start) * 1000

            max_new_tokens = settings.llm_max_new_tokens
            if device in ("mps", "cpu"):
                max_new_tokens = min(settings.llm_max_new_tokens, 256)

            self.logger.info(
                "Direct doc summary: doc_id=%s text_len=%d preview=%s",
                latest_doc.id,
                len(latest_doc_text),
                latest_doc_text[:200] + "..."
                if len(latest_doc_text) > 200
                else latest_doc_text,
            )

            greeting = (
                f"Hi {patient_first_name}," if patient_first_name else "Hi there,"
            )

            direct_prompt = (
                f"Summarize the patient's most recent document using ONLY the document text below.\n\n"
                "CRITICAL REQUIREMENTS:\n"
                f"1. You MUST start your response with exactly: '{greeting}'\n"
                "2. Use second person ('your', 'you') throughout - NEVER say 'a patient's', 'the patient's', or 'an Antenatal Profile checkup'. Say 'your antenatal checkup' instead.\n"
                "3. If you see both 'TB Screening: Positive' AND 'Screening outcome: Negative' in the document, combine them into ONE line: 'TB screening: Positive (the document also lists a screening outcome of \"Negative\"; please confirm with your clinic what this refers to)'\n"
                "4. For 'What this means' section, provide specific helpful context like: 'Your antenatal visit included routine checks, laboratory tests, and an ultrasound, all of which have been recorded in this document. Some results are clearly noted, while others may need clarification from your healthcare provider—especially where different screening outcomes are mentioned.'\n\n"
                "Output format requirements:\n"
                "- Use 3–5 short sections with bold headings like **✅ Overview**, **📋 Key results**, **❤️ What this means**, **Next steps**.\n"
                "- Use emojis sparingly ONLY in headings (✅ ❤️ 📋) — no emojis in the body.\n"
                '- Do NOT add meta text like "I understand" or "Here is the summary".\n'
                "- Use the real numbers + units exactly as written.\n"
                "- If a value is not present, do NOT invent it.\n\n"
                "Customer-friendly guidelines:\n"
                "- ALWAYS use 'your' instead of 'a patient's', 'the patient's', or 'an [X] checkup' (e.g., 'your antenatal checkup', not 'an Antenatal Profile checkup').\n"
                "- Avoid jargon: Say 'not recorded' or 'not done' instead of 'NR'.\n"
                "- For 'not tested' or 'NR Not tested': Use gentler phrasing: 'Not recorded / not done' (not 'not tested' which can sound accusatory).\n"
                "- Remove unexplained abbreviations: If you see 'HIV: R Non-Reactive', remove the 'R' unless the document explains it. Just say 'HIV: Non-Reactive'.\n"
                "- Fix common OCR errors: 'Urineysis' → 'Urinalysis', 'Isolazid' → 'Isoniazid' (if that's what the document says).\n"
                "- Handle contradictions: If you see 'TB Screening: Positive' and 'Screening outcome: Negative', combine them: 'TB screening: Positive (the document also lists a screening outcome of \"Negative\"; please confirm with your clinic what this refers to)'.\n"
                "- For lab values: Include the number and unit. If the document says it's high/low/normal, include that. If not, just state the value without interpreting.\n"
                "- For 'What this means' section: Provide helpful context about what the visit/tests included. Acknowledge that some results may need clarification from the healthcare provider. Be reassuring and supportive, not vague. Use the example provided above.\n"
                "- Use clear, simple language throughout.\n\n"
                "DOCUMENT TEXT (extracted):\n"
                f"{latest_doc_text}\n\n"
                f"Patient question: {question}\n\n"
                f"Answer (MUST start with '{greeting}'):"
            )

            generation_start = time.time()
            llm_response = await self.llm_service.generate(
                prompt=direct_prompt,
                max_new_tokens=max_new_tokens,
                temperature=decoding_profile.temperature,
                do_sample=decoding_profile.do_sample,
                top_p=decoding_profile.top_p,
                system_prompt=enhanced_system_prompt,
                conversation_history=conversation_history,
            )
            generation_time = (time.time() - generation_start) * 1000

            cleaned_response_text = llm_response.text
            cleaned_response_text = await self._self_correct_response(
                question=question,
                context_text=latest_doc_text,
                response_text=cleaned_response_text,
                decoding_profile=decoding_profile,
            )

            is_summary_query = any(
                keyword in question.lower()
                for keyword in ["summarize", "summary", "overview", "findings"]
            )

            if is_summary_query:
                if len(cleaned_response_text.strip()) < 10:
                    self.logger.warning(
                        "Summary response suspiciously short: %s",
                        cleaned_response_text[:50],
                    )
            else:
                is_valid, validation_error = self.evidence_validator.validate_response(
                    cleaned_response_text, latest_doc_text, question
                )

                if not is_valid and validation_error:
                    self.logger.warning(
                        "Response validation failed (direct summary): question=%s error=%s",
                        question,
                        validation_error,
                    )
                    cleaned_response_text = validation_error

            banned_phrases = self.evidence_validator.contains_banned_phrases(
                cleaned_response_text
            )
            if banned_phrases:
                self.logger.warning(
                    "Response contains banned phrases (possible hallucination): %s",
                    banned_phrases,
                )
                for phrase_pattern in banned_phrases:
                    cleaned_response_text = re.sub(
                        phrase_pattern,
                        "The document does not describe this.",
                        cleaned_response_text,
                        flags=re.IGNORECASE,
                    )

            if patient_first_name:
                if not re.match(
                    rf"^\s*Hi\s+{re.escape(patient_first_name)}",
                    cleaned_response_text,
                    re.IGNORECASE,
                ):
                    if re.match(r"^\s*Hi\s+", cleaned_response_text, re.IGNORECASE):
                        cleaned_response_text = re.sub(
                            r"^\s*Hi\s+[^,\n]+",
                            f"Hi {patient_first_name}",
                            cleaned_response_text,
                            flags=re.IGNORECASE,
                        )
                    else:
                        cleaned_response_text = f"Hi {patient_first_name},\n\n{cleaned_response_text.lstrip()}"
            elif not re.match(r"^\s*Hi\s+", cleaned_response_text, re.IGNORECASE):
                cleaned_response_text = f"Hi there,\n\n{cleaned_response_text.lstrip()}"

            cleaned_response_text = re.sub(
                r"(?is)^\s*(i understand[^.\n]*\.\s*)+",
                "",
                cleaned_response_text or "",
            )
            cleaned_response_text = re.sub(
                r"(?im)^\s*here is the summary:\s*",
                "",
                cleaned_response_text,
            ).lstrip()

            ocr_fixes = {
                r"\bUrineysis\b": "Urinalysis",
                r"\bIsolazid\b": "Isoniazid",
                r"\bNR\b(?!\s*[A-Z])": "not recorded",
                r"\bNR\s+Not\s+tested\b": "not recorded / not done",
            }
            for pattern, replacement in ocr_fixes.items():
                cleaned_response_text = re.sub(
                    pattern, replacement, cleaned_response_text, flags=re.IGNORECASE
                )

            cleaned_response_text = re.sub(
                r"\bHIV:\s*[A-Z]\s+Non-Reactive\b",
                "HIV: Non-Reactive",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )
            cleaned_response_text = re.sub(
                r"\bHIV:\s*[A-Z]\s+Reactive\b",
                "HIV: Reactive",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )

            cleaned_response_text = re.sub(
                r"\bnot tested\b",
                "not recorded / not done",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )

            cleaned_response_text = re.sub(
                r"\ba patient\'?s\b", "your", cleaned_response_text, flags=re.IGNORECASE
            )
            cleaned_response_text = re.sub(
                r"\bthe patient\'?s\b",
                "your",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )

            cleaned_response_text = re.sub(
                r"\ban\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+checkup\b",
                r"your \1 checkup",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )
            cleaned_response_text = re.sub(
                r"\ban\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Profile\s+checkup\b",
                r"your \1 checkup",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )
            cleaned_response_text = re.sub(
                r"summarizes\s+an\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+checkup\b",
                r"summarizes your \1 checkup",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )
            cleaned_response_text = re.sub(
                r"summarizes\s+an\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Profile\s+checkup\b",
                r"summarizes your \1 checkup",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )

            if re.search(
                r"TB\s+Screening[:\s]+Positive", cleaned_response_text, re.IGNORECASE
            ) and re.search(
                r"Screening\s+outcome[:\s]+Negative",
                cleaned_response_text,
                re.IGNORECASE,
            ):
                cleaned_response_text = re.sub(
                    r"\*\s*TB\s+Screening[:\s]+Positive\s*\n",
                    "",
                    cleaned_response_text,
                    flags=re.IGNORECASE,
                )
                cleaned_response_text = re.sub(
                    r"\*\s*Screening\s+outcome[:\s]+Negative\s*\n",
                    '* TB screening: Positive (the document also lists a screening outcome of "Negative"; please confirm with your clinic what this refers to)\n',
                    cleaned_response_text,
                    flags=re.IGNORECASE,
                )
                cleaned_response_text = re.sub(
                    r"\*\s*TB\s+Screening[:\s]+Positive[^\n]*\n\s*\*\s*Screening\s+outcome[:\s]+Negative",
                    '* TB screening: Positive (the document also lists a screening outcome of "Negative"; please confirm with your clinic what this refers to)',
                    cleaned_response_text,
                    flags=re.IGNORECASE | re.MULTILINE,
                )

            # Remove banned phrases that indicate inference without evidence
            banned_phrases = self.evidence_validator.contains_banned_phrases(
                cleaned_response_text
            )
            if banned_phrases:
                self.logger.warning(
                    "Response contains banned phrases (possible hallucination): %s",
                    banned_phrases,
                )
                # Remove or replace banned phrases
                for phrase_pattern in banned_phrases:
                    cleaned_response_text = re.sub(
                        phrase_pattern,
                        "The document does not describe this.",
                        cleaned_response_text,
                        flags=re.IGNORECASE,
                    )

            hallucination_patterns = [
                (r"further\s+testing\s+confirmed", "The document does not state this."),
                (
                    r"normal\s+findings\s+during\s+the\s+examination",
                    "The document does not describe the examination findings.",
                ),
                (r"your\s+doctor\s+will\s+review\s+this\s+result", ""),
                (
                    r"your\s+doctor\s+will\s+provide\s+more\s+detailed\s+explanations",
                    "",
                ),
                (r"to\s+determine\s+if\s+it\s+needs\s+further\s+investigation", ""),
                (r"this\s+is\s+within\s+the\s+typical\s+range", ""),
                (r"this\s+is\s+within\s+the\s+normal\s+range", ""),
                (r"performed\s+on\s+January\s+\d{1,2}(?:st|nd|rd|th)?,\s+2026", ""),
                (r"performed\s+on\s+\w+\s+\d{1,2}(?:st|nd|rd|th)?,\s+2026", ""),
            ]
            for pattern, replacement in hallucination_patterns:
                cleaned_response_text = re.sub(
                    pattern, replacement, cleaned_response_text, flags=re.IGNORECASE
                )
            cleaned_response_text = cleaned_response_text.replace(
                "--- 📄 Documents ---", ""
            )
            cleaned_response_text = cleaned_response_text.replace(
                "--- Documents ---", ""
            )
            cleaned_response_text = cleaned_response_text.replace(
                "--- 📝 Additional Notes ---", ""
            )

            # Remove [Redacted] placeholders more aggressively
            cleaned_response_text = re.sub(
                r"\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?",
                "",
                cleaned_response_text,
            )
            cleaned_response_text = cleaned_response_text.replace("[Redacted]", "")

            # Remove template-style placeholders (but only if they're actual placeholders, not real values)
            cleaned_response_text = re.sub(
                r"(?i)\[insert[^]]+here\]", "", cleaned_response_text
            )
            cleaned_response_text = re.sub(
                r"(?i)\[mention[^\]]*e\.g\.[^\]]+\]", "", cleaned_response_text
            )

            # Remove specific placeholder patterns like [Pulse Rate Value], [Value], etc.
            cleaned_response_text = re.sub(
                r"\[[^\]]*[Vv]alue[^\]]*\]",
                "The document does not record this information.",
                cleaned_response_text,
            )
            cleaned_response_text = re.sub(
                r"\[[^\]]*[Pp]ulse[^\]]*[Rr]ate[^\]]*\]",
                "The document does not record your pulse rate.",
                cleaned_response_text,
            )
            cleaned_response_text = re.sub(
                r"\[[^\]]*[Bb]lood[^\]]*[Pp]ressure[^\]]*\]",
                "The document does not record your blood pressure.",
                cleaned_response_text,
            )
            cleaned_response_text = re.sub(
                r"\[[^\]]*[Tt]emperature[^\]]*\]",
                "The document does not record your temperature.",
                cleaned_response_text,
            )
            cleaned_response_text = re.sub(
                r"\[[^\]]*[Pp]atient[^\]]*[Nn]ame[^\]]*\]", "", cleaned_response_text
            )

            cleaned_response_text = re.sub(
                r"([^.?!]*\bpulse rate was measured at)\s+(?![0-9])bpm([^.?!]*\.)",
                r"\1, but the document doesn't list the exact number\2",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )
            cleaned_response_text = re.sub(
                r"([^.?!]*\btemperature was recorded as)\s+(?![0-9])°c([^.?!]*\.)",
                r"\1, but the exact value isn't clearly written\2",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )
            cleaned_response_text = re.sub(
                r"([^.?!]*\bblood pressure was measured at)\s+(?![0-9])mmhg([^.?!]*\.)",
                r"\1, but it doesn't show the exact reading\2",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )

            if re.search(
                r"\d+\s*(bpm|mmhg|°c|°f|g/dl|mg/dl|mEq/L)",
                cleaned_response_text,
                re.IGNORECASE,
            ):
                cleaned_response_text = re.sub(
                    r"the document does not specify the exact value for these measurements\.",
                    "",
                    cleaned_response_text,
                    flags=re.IGNORECASE,
                )

            cleaned_response_text = re.sub(
                r"\(\d{4}-\d{2}-\d{2}\)", "", cleaned_response_text
            )

            lines = cleaned_response_text.split("\n")
            filtered_lines = []
            skip_section = False
            section_headers = [
                "dates and timestamps",
                "dates",
                "timestamps",
                "summary",
                "dates:",
                "timestamps:",
                "summary:",
                "next visit",
                "next visit:",
                "dates and timestamps:",
            ]

            for line in lines:
                stripped = line.strip()

                if skip_section and not stripped:
                    continue

                if stripped.startswith("---") and (
                    "📄" in stripped or "Documents" in stripped or "Notes" in stripped
                ):
                    skip_section = True
                    continue

                if any(header in stripped.lower() for header in section_headers):
                    skip_section = True
                    continue

                if re.match(r"^\(?\d{4}-\d{2}-\d{2}\)?$", stripped):
                    continue

                if re.match(r"^\[.*[Rr]edacted.*\]$", stripped):
                    continue

                if skip_section and stripped:
                    is_metadata = (
                        stripped.startswith("*")
                        or stripped.startswith("-")
                        or stripped.startswith("•")
                        or (stripped.startswith("(") and re.search(r"\d{4}", stripped))
                        or any(
                            keyword in stripped.lower()
                            for keyword in [
                                "date:",
                                "timestamp:",
                                "next visit:",
                                "redacted",
                            ]
                        )
                    )
                    if not is_metadata:
                        skip_section = False

                if not skip_section:
                    filtered_lines.append(line)

            cleaned_response_text = "\n".join(filtered_lines).strip()

            lines = cleaned_response_text.split("\n")
            if lines:
                last_line = lines[-1].strip()
                if last_line.endswith(",") and len(last_line) < 50:
                    lines = lines[:-1]
                cleaned_response_text = "\n".join(lines).strip()

            disclaimer_patterns = [
                r"disclaimer.*intended for informational purposes only.*",
                r"always consult with your healthcare provider for personalized medical advice.*",
                r"if you have any questions about these results, please consult with a healthcare professional.*",
            ]
            for pat in disclaimer_patterns:
                cleaned_response_text = re.sub(
                    pat, "", cleaned_response_text, flags=re.IGNORECASE | re.DOTALL
                )

            cleaned_response_text = re.sub(r"[ \t]+", " ", cleaned_response_text)
            cleaned_response_text = re.sub(
                r"\s*\n\s*", "\n", cleaned_response_text
            ).strip()
            cleaned_response_text = self._enforce_numeric_grounding(
                response_text=cleaned_response_text,
                context_text=latest_doc_text,
                question=question,
            )
            direct_doc_sources_summary = [
                {
                    "source_type": "document",
                    "source_id": latest_doc.id,
                    "relevance": 1.0,
                    "snippet_excerpt": latest_doc_text[:320]
                    + ("..." if len(latest_doc_text) > 320 else ""),
                }
            ]
            cleaned_response_text = self._append_numeric_claim_citations(
                response_text=cleaned_response_text,
                sources_summary=direct_doc_sources_summary,
            )
            cleaned_response_text = self._enforce_clinician_numeric_citations(
                response_text=cleaned_response_text,
                question=question,
                clinician_mode=clinician_mode,
            )

            cleaned_llm_response = LLMResponse(
                text=cleaned_response_text,
                tokens_generated=llm_response.tokens_generated,
                tokens_input=llm_response.tokens_input,
                generation_time_ms=llm_response.generation_time_ms,
                finish_reason=llm_response.finish_reason,
            )
            llm_response = cleaned_llm_response

            self.logger.info(
                "RAG direct doc summary done device=%s tokens_generated=%s time_ms=%.1f",
                device,
                llm_response.tokens_generated,
                generation_time,
            )

            # Add assistant message
            assistant_message = await self.conversation_manager.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=llm_response.text,
            )

            total_time = (time.time() - total_start) * 1000

            return RAGResponse(
                answer=llm_response.text,
                llm_response=llm_response,
                context_used=latest_doc_text[:500] + "..."
                if len(latest_doc_text) > 500
                else latest_doc_text,
                num_sources=1,
                sources_summary=direct_doc_sources_summary,  # type: ignore[union-attr]
                conversation_id=conversation_id,
                message_id=assistant_message.message_id,
                context_time_ms=context_time,
                generation_time_ms=generation_time,
                total_time_ms=total_time,
            )
        else:
            context_result = await self.context_engine.get_context(
                query=question,
                patient_id=patient_id,
                max_tokens=effective_max_context_tokens,
                system_prompt=enhanced_system_prompt,
                min_score=min_score,
            )

        if context_result is not None:
            self.logger.info("Context chars=%s", len(context_result.prompt))
            context_time = (time.time() - context_start) * 1000
            self.logger.info(
                "RAG context built device=%s context_tokens=%s time_ms=%.1f",
                device,
                effective_max_context_tokens,
                context_time,
            )
            decoding_profile = self._decoding_profile_for_query(
                question=question,
                routing=routing,
                context_result=context_result,
            )
            strict_violation, top_score = self._strict_grounding_violation(
                context_result
            )
            if strict_violation:
                if (
                    top_score >= settings.llm_low_confidence_floor
                    and context_result.synthesized_context.total_chunks_used > 0
                ):
                    answer = self._build_low_confidence_inference(context_result)
                    finish_reason = "strict_grounding_low_confidence"
                    self._record_guardrail_event(
                        "strict_grounding_low_confidence",
                        mode="ask",
                    )
                else:
                    answer = self.STRICT_GROUNDING_REFUSAL
                    finish_reason = "strict_grounding_no_evidence"
                    self._record_guardrail_event(
                        "strict_grounding_no_evidence",
                        mode="ask",
                    )
                self.logger.warning(
                    "Strict grounding refusal: patient=%s question=%s top_score=%.3f threshold=%.3f",
                    patient_id,
                    question,
                    top_score,
                    settings.llm_min_relevance_score,
                )
                assistant_message = await self.conversation_manager.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer,
                )
                sources_summary = self._build_sources_summary(
                    context_result.ranked_results
                )
                return RAGResponse(
                    answer=answer,
                    llm_response=LLMResponse(
                        text=answer,
                        tokens_generated=0,
                        tokens_input=0,
                        generation_time_ms=0.0,
                        finish_reason=finish_reason,
                    ),
                    context_used=context_result.synthesized_context.full_context,
                    num_sources=context_result.synthesized_context.total_chunks_used,
                    sources_summary=sources_summary,
                    conversation_id=conversation_id,
                    message_id=assistant_message.message_id,
                    context_time_ms=context_time,
                    generation_time_ms=0.0,
                    total_time_ms=(time.time() - total_start) * 1000,
                )

            context_text = context_result.synthesized_context.full_context
            is_summary_query = any(
                keyword in question.lower()
                for keyword in [
                    "summarize",
                    "summary",
                    "overview",
                    "findings",
                    "key information",
                    "what information",
                    "what does",
                ]
            )

            if not is_summary_query:
                can_answer, reason_if_no = (
                    self.evidence_validator.can_answer_from_context(
                        question, context_text
                    )
                )

                if not can_answer:
                    if question_mode == "GENERAL_MEDICAL":
                        reason_if_no = (
                            "The document does not explain this topic. "
                            "I can provide a general explanation if you'd like, "
                            "but it won't be from your medical records."
                        )
                        self._record_guardrail_event(
                            "general_medical_no_evidence",
                            mode="ask",
                        )
                    else:
                        self._record_guardrail_event(
                            "evidence_gating_blocked",
                            mode="ask",
                        )
                    self.logger.warning(
                        "Evidence gating blocked answer: question=%s reason=%s",
                        question,
                        reason_if_no,
                    )
                    assistant_message = await self.conversation_manager.add_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=reason_if_no
                        or "The document does not record this information.",
                    )
                    return RAGResponse(
                        answer=reason_if_no
                        or "The document does not record this information.",
                        llm_response=LLMResponse(
                            text=reason_if_no
                            or "The document does not record this information.",
                            tokens_generated=0,
                            tokens_input=0,
                            generation_time_ms=0,
                            finish_reason="general_medical_no_evidence"
                            if question_mode == "GENERAL_MEDICAL"
                            else "evidence_gating",
                        ),
                        context_used=context_text,
                        num_sources=context_result.synthesized_context.total_chunks_used,
                        sources_summary=[],
                        conversation_id=conversation_id,
                        message_id=assistant_message.message_id,
                        context_time_ms=context_time,
                        generation_time_ms=0,
                        total_time_ms=context_time,
                    )
            else:
                if not context_text or len(context_text.strip()) < 5:
                    self.logger.warning("Summary query but context is empty")
                    assistant_message = await self.conversation_manager.add_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content="No relevant information found in the patient's records to summarize.",
                    )
                    return RAGResponse(
                        answer="No relevant information found in the patient's records to summarize.",
                        llm_response=LLMResponse(
                            text="No relevant information found in the patient's records to summarize.",
                            tokens_generated=0,
                            tokens_input=0,
                            generation_time_ms=0,
                            finish_reason="empty_context",
                        ),
                        context_used=context_text or "",
                        num_sources=0,
                        sources_summary=[],
                        conversation_id=conversation_id,
                        message_id=assistant_message.message_id,
                        context_time_ms=context_time,
                        generation_time_ms=0,
                        total_time_ms=context_time,
                    )

            if question_mode == "GENERAL_MEDICAL":
                question_terms = set(re.findall(r"\b\w+\b", question.lower()))
                context_terms = set(re.findall(r"\b\w+\b", context_text.lower()))
                overlap = question_terms.intersection(context_terms)

                if len(overlap) / max(len(question_terms), 1) < 0.3:
                    self.logger.info(
                        "General medical question with low context overlap, will note this in response"
                    )

        if not context_result.synthesized_context.total_chunks_used:
            if question_mode == "GENERAL_MEDICAL":
                answer = (
                    "The document does not explain this topic. "
                    "I can provide a general explanation if you'd like, "
                    "but it won't be from your medical records."
                )
                self._record_guardrail_event(
                    "general_medical_no_evidence",
                    mode="ask",
                )
                assistant_message = await self.conversation_manager.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer,
                )
                return RAGResponse(
                    answer=answer,
                    llm_response=LLMResponse(
                        text=answer,
                        tokens_generated=0,
                        tokens_input=0,
                        generation_time_ms=0.0,
                        finish_reason="general_medical_no_evidence",
                    ),
                    context_used=context_result.synthesized_context.full_context,
                    num_sources=0,
                    sources_summary=[],
                    conversation_id=conversation_id,
                    message_id=assistant_message.message_id,
                    context_time_ms=context_time,
                    generation_time_ms=0.0,
                    total_time_ms=(time.time() - total_start) * 1000,
                )

            result = await self.db.execute(
                select(func.count(MemoryChunk.id)).where(
                    MemoryChunk.patient_id == patient_id
                )
            )
            total_chunks = result.scalar() or 0

            result = await self.db.execute(
                select(func.count(MemoryChunk.id)).where(
                    MemoryChunk.patient_id == patient_id,
                    MemoryChunk.is_indexed.is_(True),
                )
            )
            indexed_chunks = result.scalar() or 0

            retrieval_results_count = (
                len(context_result.ranked_results)
                if hasattr(context_result, "ranked_results")
                else 0
            )
            max_similarity = 0.0
            if (
                hasattr(context_result, "ranked_results")
                and context_result.ranked_results
            ):
                max_similarity = max(
                    (r.final_score for r in context_result.ranked_results), default=0.0
                )

            if total_chunks == 0:
                answer = (
                    "No relevant information could be retrieved because this patient "
                    "has no processed records or document chunks yet. "
                    "Upload and process documents or add structured data first."
                )
            elif indexed_chunks == 0:
                answer = (
                    "No relevant information could be retrieved. This patient has "
                    f"{total_chunks} document chunks, but none are indexed for semantic search. "
                    "This usually means embedding generation or indexing failed. "
                    "Reprocess the patient's documents or retry indexing."
                )
            elif retrieval_results_count > 0 and max_similarity > 0:
                answer = (
                    f"Found {retrieval_results_count} potentially relevant chunks, but the similarity "
                    f"score ({max_similarity:.2f}) was below the threshold. "
                    "The question might not match the document content semantically. "
                    "Try asking more general questions like 'What information is in the document?' "
                    "or 'Summarize the document contents.'"
                )
            else:
                answer = (
                    "No relevant information matching this question was found in the "
                    f"patient's indexed records (about {indexed_chunks} chunks). "
                    "Try rephrasing the question using different words, or ask more general questions "
                    "like 'What does the document say?' or 'Summarize the document.'"
                )

            assistant_message = await self.conversation_manager.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
            )
            return RAGResponse(
                answer=answer,
                llm_response=LLMResponse(
                    text=answer,
                    tokens_generated=0,
                    tokens_input=0,
                    generation_time_ms=0.0,
                ),
                context_used=context_result.synthesized_context.full_context,
                num_sources=0,
                sources_summary=[],
                conversation_id=conversation_id,
                message_id=assistant_message.message_id,
                context_time_ms=context_time,
                generation_time_ms=0.0,
                total_time_ms=(time.time() - total_start) * 1000,
            )

        direct_structured_answer = self._build_direct_structured_answer(
            question=question,
            context_result=context_result,
        )
        if direct_structured_answer:
            self.logger.info(
                "Using deterministic structured answer for question=%s", question
            )
            sources_summary = self._build_sources_summary(context_result.ranked_results)
            direct_structured_answer = self._append_numeric_claim_citations(
                response_text=direct_structured_answer,
                sources_summary=sources_summary,
            )
            self._record_guardrail_event("structured_direct", mode="ask")
            assistant_message = await self.conversation_manager.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=direct_structured_answer,
            )
            return RAGResponse(
                answer=direct_structured_answer,
                llm_response=LLMResponse(
                    text=direct_structured_answer,
                    tokens_generated=0,
                    tokens_input=0,
                    generation_time_ms=0.0,
                    finish_reason="structured_direct",
                ),
                context_used=context_result.synthesized_context.full_context,
                num_sources=context_result.synthesized_context.total_chunks_used,
                sources_summary=sources_summary,
                conversation_id=conversation_id,
                message_id=assistant_message.message_id,
                context_time_ms=context_time,
                generation_time_ms=0.0,
                total_time_ms=(time.time() - total_start) * 1000,
            )

        # Build sources summary
        if context_result is not None:
            sources_summary = self._build_sources_summary(context_result.ranked_results)

        # Generate answer using the full prompt with context
        generation_start = time.time()
        if context_result is not None:
            max_new_tokens = settings.llm_max_new_tokens
            if device in ("mps", "cpu"):
                max_new_tokens = min(settings.llm_max_new_tokens, 256)

            clean_prompt = context_result.prompt
            clean_prompt = clean_prompt.replace("--- 📄 Documents ---", "")
            clean_prompt = clean_prompt.replace("--- Documents ---", "")
            clean_prompt = clean_prompt.replace("--- 📝 Additional Notes ---", "")
            clean_prompt = re.sub(
                r"\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?",
                "",
                clean_prompt,
            )

            if question_mode == "GENERAL_MEDICAL":
                clean_prompt = (
                    f"{clean_prompt}\n\n"
                    "IMPORTANT: The user is asking a general medical question. "
                    "If this information is NOT explicitly in the document context above, "
                    "you must say: 'The document does not explain [topic]. "
                    "I can provide a general explanation if you'd like, but it won't be from your medical records.' "
                    "Do NOT automatically provide general medical knowledge unless the user explicitly asks for it."
                )
            else:
                few_shot_block = self._build_grounded_few_shot_block(
                    context_result=context_result,
                    clinician_mode=clinician_mode,
                )
                if few_shot_block:
                    clean_prompt = f"{few_shot_block}\n\n{clean_prompt}"

            llm_response = await self.llm_service.generate(
                prompt=clean_prompt,
                max_new_tokens=max_new_tokens,
                temperature=decoding_profile.temperature,
                do_sample=decoding_profile.do_sample,
                top_p=decoding_profile.top_p,
                conversation_history=conversation_history,
            )

        cleaned_response_text = llm_response.text
        cleaned_response_text = await self._self_correct_response(
            question=question,
            context_text=context_text,
            response_text=cleaned_response_text,
            decoding_profile=decoding_profile,
        )

        is_valid, validation_error = self.evidence_validator.validate_response(
            cleaned_response_text, context_text, question
        )

        if not is_valid and validation_error:
            self.logger.warning(
                "Response validation failed: question=%s error=%s",
                question,
                validation_error,
            )
            cleaned_response_text = validation_error

        cleaned_response_text = cleaned_response_text.replace(
            "--- 📄 Documents ---", ""
        )
        cleaned_response_text = cleaned_response_text.replace("--- Documents ---", "")
        cleaned_response_text = cleaned_response_text.replace(
            "--- 📝 Additional Notes ---", ""
        )

        cleaned_response_text = re.sub(
            r"\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?", "", cleaned_response_text
        )
        cleaned_response_text = cleaned_response_text.replace("[Redacted]", "")

        cleaned_response_text = re.sub(
            r"\[[^\]]*[Vv]alue[^\]]*\]",
            "The document does not record this information.",
            cleaned_response_text,
        )
        cleaned_response_text = re.sub(
            r"\[[^\]]*[Pp]ulse[^\]]*[Rr]ate[^\]]*\]",
            "The document does not record your pulse rate.",
            cleaned_response_text,
        )
        cleaned_response_text = re.sub(
            r"\[[^\]]*[Bb]lood[^\]]*[Pp]ressure[^\]]*\]",
            "The document does not record your blood pressure.",
            cleaned_response_text,
        )
        cleaned_response_text = re.sub(
            r"\[[^\]]*[Tt]emperature[^\]]*\]",
            "The document does not record your temperature.",
            cleaned_response_text,
        )
        cleaned_response_text = re.sub(
            r"\[[^\]]*[Pp]atient[^\]]*[Nn]ame[^\]]*\]", "", cleaned_response_text
        )

        cleaned_response_text = re.sub(
            r"(?i)\[insert[^]]+here\]", "", cleaned_response_text
        )
        cleaned_response_text = re.sub(
            r"(?i)\[mention[^\]]*e\.g\.[^\]]+\]", "", cleaned_response_text
        )
        cleaned_response_text = re.sub(r"\bof\s{2,}bpm\b", "bpm", cleaned_response_text)
        cleaned_response_text = re.sub(
            r"[^.?!]*\bpulse rate was measured at\s*bpm[^.?!]*\.",
            "The document shows that your pulse rate was measured, but it doesn't list the exact number.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )
        cleaned_response_text = re.sub(
            r"[^.?!]*\btemperature was recorded as\s*°c[^.?!]*\.",
            "The document notes that your temperature was checked, but the exact value isn't clearly written.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )
        cleaned_response_text = re.sub(
            r"[^.?!]*\bblood pressure was measured at\s*mmhg[^.?!]*\.",
            "The document indicates that your blood pressure was measured, but it doesn't show the exact reading.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )

        cleaned_response_text = re.sub(
            r"\bpulse rate was recorded as\s+\*+\s+beats per minute",
            "The document does not record your pulse rate.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )
        cleaned_response_text = re.sub(
            r"\bpulse rate was\s+\*+\s+beats per minute",
            "The document does not record your pulse rate.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )

        # Remove hallucinated interpretations that aren't in the document
        hallucination_patterns = [
            (r"further\s+testing\s+confirmed", "The document does not state this."),
            (
                r"normal\s+findings\s+during\s+the\s+examination",
                "The document does not describe the examination findings.",
            ),
            (r"your\s+doctor\s+will\s+review\s+this\s+result", ""),
            (r"your\s+doctor\s+will\s+provide\s+more\s+detailed\s+explanations", ""),
            (r"to\s+determine\s+if\s+it\s+needs\s+further\s+investigation", ""),
            (r"this\s+is\s+within\s+the\s+typical\s+range", ""),
            (r"this\s+is\s+within\s+the\s+normal\s+range", ""),
            (
                r"performed\s+on\s+January\s+\d{1,2}(?:st|nd|rd|th)?,\s+2026",
                "",
            ),  # Remove invented dates
            (
                r"performed\s+on\s+\w+\s+\d{1,2}(?:st|nd|rd|th)?,\s+2026",
                "",
            ),  # Remove invented dates
        ]
        for pattern, replacement in hallucination_patterns:
            cleaned_response_text = re.sub(
                pattern, replacement, cleaned_response_text, flags=re.IGNORECASE
            )

        cleaned_response_text = re.sub(
            r"\btemperature was recorded as\s+\*+\s*°c",
            "The document does not record your temperature.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )
        cleaned_response_text = re.sub(
            r"\bblood pressure was recorded as\s+\*+\s*mmhg",
            "The document does not record your blood pressure.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )

        # Remove any remaining placeholder patterns
        cleaned_response_text = re.sub(
            r"\b\w+\s+was\s+(recorded|measured|checked)\s+as\s+\*{2,}",
            lambda m: f"The document does not record your {m.group(0).split()[0]}.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )

        cleaned_response_text = re.sub(
            r"\(\d{4}-\d{2}-\d{2}\)", "", cleaned_response_text
        )

        lines = cleaned_response_text.split("\n")
        filtered_lines = []
        skip_section = False
        section_headers = [
            "dates and timestamps",
            "dates",
            "timestamps",
            "summary",
            "dates:",
            "timestamps:",
            "summary:",
            "next visit",
            "next visit:",
            "dates and timestamps:",
        ]

        for line in lines:
            stripped = line.strip()

            # Skip empty lines if we're in skip mode
            if skip_section and not stripped:
                continue

            # Skip section marker lines
            if stripped.startswith("---") and (
                "📄" in stripped or "Documents" in stripped or "Notes" in stripped
            ):
                skip_section = True
                continue

            # Skip section headers
            if any(header in stripped.lower() for header in section_headers):
                skip_section = True
                continue

            # Skip lines that are just date patterns or metadata
            if re.match(r"^\(?\d{4}-\d{2}-\d{2}\)?$", stripped):
                continue

            # Skip lines that are just "[Redacted]" or similar
            if re.match(r"^\[.*[Rr]edacted.*\]$", stripped):
                continue

            # End skip mode when we hit real content
            if skip_section and stripped:
                # Real content is not a list item starting with *, -, •, or (
                # and doesn't contain common metadata keywords
                is_metadata = (
                    stripped.startswith("*")
                    or stripped.startswith("-")
                    or stripped.startswith("•")
                    or (stripped.startswith("(") and re.search(r"\d{4}", stripped))
                    or any(
                        keyword in stripped.lower()
                        for keyword in [
                            "date:",
                            "timestamp:",
                            "next visit:",
                            "redacted",
                        ]
                    )
                )
                if not is_metadata:
                    skip_section = False

            if not skip_section:
                filtered_lines.append(line)

            cleaned_response_text = "\n".join(filtered_lines).strip()

        lines = cleaned_response_text.split("\n")
        if lines:
            last_line = lines[-1].strip()
            if last_line.endswith(",") and len(last_line) < 50:
                lines = lines[:-1]
            cleaned_response_text = "\n".join(lines).strip()

        disclaimer_patterns = [
            r"disclaimer.*intended for informational purposes only.*",
            r"always consult with your healthcare provider for personalized medical advice.*",
            r"if you have any questions about these results, please consult with a healthcare professional.*",
        ]
        for pat in disclaimer_patterns:
            cleaned_response_text = re.sub(
                pat, "", cleaned_response_text, flags=re.IGNORECASE | re.DOTALL
            )

        # Clean up multiple spaces and normalize whitespace
        cleaned_response_text = re.sub(r"[ \t]+", " ", cleaned_response_text)
        cleaned_response_text = re.sub(r"\s*\n\s*", "\n", cleaned_response_text).strip()
        cleaned_response_text = self._enforce_numeric_grounding(
            response_text=cleaned_response_text,
            context_text=context_text,
            question=question,
        )
        cleaned_response_text = self._append_numeric_claim_citations(
            response_text=cleaned_response_text,
            sources_summary=sources_summary,
        )
        cleaned_response_text = self._enforce_clinician_numeric_citations(
            response_text=cleaned_response_text,
            question=question,
            clinician_mode=clinician_mode,
        )

        # Create cleaned response
        cleaned_llm_response = LLMResponse(
            text=cleaned_response_text,
            tokens_generated=llm_response.tokens_generated,
            tokens_input=llm_response.tokens_input,
            generation_time_ms=llm_response.generation_time_ms,
            finish_reason=llm_response.finish_reason,
        )
        llm_response = cleaned_llm_response
        generation_time = (time.time() - generation_start) * 1000
        self.logger.info(
            "RAG generation done device=%s tokens_generated=%s time_ms=%.1f",
            device,
            llm_response.tokens_generated,
            generation_time,
        )

        # Add assistant message
        assistant_message = await self.conversation_manager.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=llm_response.text,
        )

        total_time = (time.time() - total_start) * 1000

        return RAGResponse(
            answer=llm_response.text,
            llm_response=llm_response,
            context_used=context_result.synthesized_context.full_context,
            num_sources=context_result.synthesized_context.total_chunks_used,
            sources_summary=sources_summary,
            conversation_id=conversation_id,
            message_id=assistant_message.message_id,
            context_time_ms=context_time,
            generation_time_ms=generation_time,
            total_time_ms=total_time,
        )

    async def stream_ask(
        self,
        question: str,
        patient_id: int,
        conversation_id: UUID | None = None,
        system_prompt: str | None = None,
        max_context_tokens: int = 4000,
    ):
        """Stream answer generation.

        Yields:
            Text chunks as they are generated
        """
        self._set_stream_metadata()

        # Fetch patient information for personalized greeting
        patient_first_name = None
        if self.db is not None:
            patient_result = await self.db.execute(
                select(Patient).where(Patient.id == patient_id)
            )
            patient = patient_result.scalar_one_or_none()
            patient_first_name = patient.first_name if patient else None

        # Get or create conversation
        if conversation_id:
            conversation = await self.conversation_manager.get_conversation(
                conversation_id
            )
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = await self.conversation_manager.create_conversation(
                patient_id
            )
            conversation_id = conversation.conversation_id

        # Add user message
        await self.conversation_manager.add_message(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )
        conversation_history = conversation.get_last_n_turns(n=3)
        routing = self.query_router.route(question, conversation_history)
        self.logger.info(
            "Stream query routed: task=%s confidence=%.2f entities=%s",
            routing.task.value,
            routing.confidence,
            routing.extracted_entities,
        )
        decoding_profile = self._decoding_profile_for_query(
            question=question,
            routing=routing,
            context_result=None,
        )

        # Get context
        device = getattr(self.llm_service, "device", None)
        if not device:
            device = "cuda" if hasattr(self.llm_service, "stream_generate") else "cpu"
        effective_max_context_tokens = max_context_tokens
        if device in ("mps", "cpu"):
            effective_max_context_tokens = min(max_context_tokens, 2000)

        # For summary/document/specialized task queries, use a lower similarity threshold
        min_score = 0.3
        enhanced_system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        clinician_mode = self._is_clinician_mode(enhanced_system_prompt)
        question_mode = self.evidence_validator.detect_question_mode(question)

        is_summary_query = routing.task == QueryTask.DOC_SUMMARY or any(
            keyword in question.lower()
            for keyword in [
                "summarize",
                "summary",
                "overview",
                "findings",
                "key information",
                "clear",
                "easy-to-understand",
            ]
        )
        is_document_query = routing.task == QueryTask.VISION_EXTRACTION or any(
            keyword in question.lower()
            for keyword in [
                "document",
                "image",
                "picture",
                "photo",
                "scan",
                "report",
                "what does",
                "what is in",
                "what information",
            ]
        )
        is_trend_query = routing.task == QueryTask.TREND_ANALYSIS
        is_med_reconciliation_query = (
            routing.task == QueryTask.MEDICATION_RECONCILIATION
        )
        is_lab_interpretation_query = routing.task == QueryTask.LAB_INTERPRETATION

        if (
            is_summary_query
            or is_document_query
            or is_trend_query
            or is_med_reconciliation_query
            or is_lab_interpretation_query
        ):
            min_score = 0.2  # Lower threshold to capture more content
            # Add extra guidance for patient-friendly summaries
            if is_summary_query:
                enhanced_system_prompt = (
                    "You are a caring health companion creating a personalized summary that puts the patient first. "
                    "Think like a product designer - make it beautiful, easy to understand, and empowering.\n\n"
                    "Key principles:\n"
                    "- Lead with what matters most to the patient\n"
                    "- Start with good news when possible\n"
                    "- Make it feel like a conversation, not a report\n"
                    "- Use natural language: 'your blood iron' not 'hemoglobin levels'\n"
                    "- Be encouraging and supportive\n"
                    "- Structure it so it's easy to scan quickly\n"
                    "- End with a warm, supportive closing\n"
                    "- ALWAYS show actual medical values (pulse rate, blood pressure, lab results, etc.) - never use [Redacted] or hide this information\n"
                    "- ONLY use numbers and values that appear in the retrieved document context - NEVER make up or guess values\n"
                    "- If a specific number is not in the documents, say 'the document doesn't specify the exact value' rather than inventing one\n\n"
                    + self.DEFAULT_SYSTEM_PROMPT
                )
        task_instruction = self._build_task_instruction(routing)
        if task_instruction:
            enhanced_system_prompt = f"{enhanced_system_prompt}\n\n{task_instruction}"

        # Special case (streaming): summaries of the "most recent/latest document" should be grounded
        # in the actual latest processed document text (not just vector retrieval), to avoid generic output.
        wants_latest_doc_summary = is_summary_query and any(
            phrase in question.lower()
            for phrase in [
                "most recent document",
                "latest document",
                "most recent file",
                "latest file",
                "most recent upload",
                "latest upload",
            ]
        )
        if wants_latest_doc_summary:
            latest_doc_result = await self.db.execute(
                select(Document)
                .where(
                    Document.patient_id == patient_id,
                    Document.processing_status == "completed",
                    Document.extracted_text.is_not(None),
                )
                .order_by(Document.received_date.desc())
                .limit(1)
            )
            latest_doc = latest_doc_result.scalar_one_or_none()
            latest_doc_text = (
                latest_doc.extracted_text.strip()
                if latest_doc
                and latest_doc.extracted_text
                and latest_doc.extracted_text.strip()
                else None
            )
            if latest_doc_text:
                # Build personalized greeting
                greeting = (
                    f"Hi {patient_first_name}," if patient_first_name else "Hi there,"
                )

                direct_prompt = (
                    f"Summarize the patient's most recent document using ONLY the document text below.\n\n"
                    "CRITICAL REQUIREMENTS:\n"
                    f"1. You MUST start your response with exactly: '{greeting}'\n"
                    "2. Use second person ('your', 'you') throughout - NEVER say 'a patient's', 'the patient's', or 'an Antenatal Profile checkup'. Say 'your antenatal checkup' instead.\n"
                    "3. If you see both 'TB Screening: Positive' AND 'Screening outcome: Negative' in the document, combine them into ONE line: 'TB screening: Positive (the document also lists a screening outcome of \"Negative\"; please confirm with your clinic what this refers to)'\n"
                    "4. For 'What this means' section, provide specific helpful context like: 'Your antenatal visit included routine checks, laboratory tests, and an ultrasound, all of which have been recorded in this document. Some results are clearly noted, while others may need clarification from your healthcare provider—especially where different screening outcomes are mentioned.'\n\n"
                    "Output format requirements:\n"
                    "- Use 3–5 short sections with bold headings like **✅ Overview**, **📋 Key results**, **❤️ What this means**, **Next steps**.\n"
                    "- Use emojis sparingly ONLY in headings (✅ ❤️ 📋) — no emojis in the body.\n"
                    '- Do NOT add meta text like "I understand" or "Here is the summary".\n'
                    "- Use the real numbers + units exactly as written.\n"
                    "- If a value is not present, do NOT invent it.\n\n"
                    "Customer-friendly guidelines:\n"
                    "- ALWAYS use 'your' instead of 'a patient's', 'the patient's', or 'an [X] checkup' (e.g., 'your antenatal checkup', not 'an Antenatal Profile checkup').\n"
                    "- Avoid jargon: Say 'not recorded' or 'not done' instead of 'NR'.\n"
                    "- For 'not tested' or 'NR Not tested': Use gentler phrasing: 'Not recorded / not done' (not 'not tested' which can sound accusatory).\n"
                    "- Remove unexplained abbreviations: If you see 'HIV: R Non-Reactive', remove the 'R' unless the document explains it. Just say 'HIV: Non-Reactive'.\n"
                    "- Fix common OCR errors: 'Urineysis' → 'Urinalysis', 'Isolazid' → 'Isoniazid' (if that's what the document says).\n"
                    "- Handle contradictions: If you see 'TB Screening: Positive' and 'Screening outcome: Negative', combine them: 'TB screening: Positive (the document also lists a screening outcome of \"Negative\"; please confirm with your clinic what this refers to)'.\n"
                    "- For lab values: Include the number and unit. If the document says it's high/low/normal, include that. If not, just state the value without interpreting.\n"
                    "- For 'What this means' section: Provide helpful context about what the visit/tests included. Acknowledge that some results may need clarification from the healthcare provider. Be reassuring and supportive, not vague. Use the example provided above.\n"
                    "- Use clear, simple language throughout.\n\n"
                    "DOCUMENT TEXT (extracted):\n"
                    f"{latest_doc_text}\n\n"
                    f"Patient question: {question}\n\n"
                    f"Answer (MUST start with '{greeting}'):"
                )

                llm_response = await self.llm_service.generate(
                    prompt=direct_prompt,
                    max_new_tokens=min(settings.llm_max_new_tokens, 256)
                    if device in ("mps", "cpu")
                    else settings.llm_max_new_tokens,
                    temperature=decoding_profile.temperature,
                    do_sample=decoding_profile.do_sample,
                    top_p=decoding_profile.top_p,
                    system_prompt=enhanced_system_prompt,
                    conversation_history=None,
                )
                text = (llm_response.text or "").strip()
                text = await self._self_correct_response(
                    question=question,
                    context_text=latest_doc_text,
                    response_text=text,
                    decoding_profile=decoding_profile,
                )

                # Strip obvious artifacts/placeholders/disclaimers.
                text = (
                    text.replace("--- 📄 Documents ---", "")
                    .replace("--- Documents ---", "")
                    .replace("--- 📝 Additional Notes ---", "")
                )
                text = re.sub(
                    r"\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?", "", text
                )
                text = text.replace("[Redacted]", "")
                text = re.sub(r"(?i)\[insert[^]]+here\]", "", text)
                text = re.sub(r"(?i)\[mention[^\]]*e\.g\.[^\]]+\]", "", text)
                # Remove common "meta" preambles
                text = re.sub(r"(?is)^\s*(i understand[^.\n]*\.\s*)+", "", text)
                text = re.sub(r"(?im)^\s*here is the summary:\s*", "", text).lstrip()
                text = re.sub(
                    r"if you have any questions about these results, please consult with a healthcare professional\.?",
                    "",
                    text,
                    flags=re.IGNORECASE,
                )
                text = re.sub(
                    r"always consult with your healthcare provider for personalized medical advice.*",
                    "",
                    text,
                    flags=re.IGNORECASE | re.DOTALL,
                )

                # Fix common OCR/spelling errors for customer-friendliness
                ocr_fixes = {
                    r"\bUrineysis\b": "Urinalysis",
                    r"\bIsolazid\b": "Isoniazid",  # Only if context suggests it's a medication
                    r"\bNR\b(?!\s*[A-Z])": "not recorded",  # Replace standalone "NR" but not "NR Not tested"
                    r"\bNR\s+Not\s+tested\b": "not recorded / not done",  # Gentler phrasing
                }
                for pattern, replacement in ocr_fixes.items():
                    text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

                # Remove banned phrases that indicate inference without evidence
                banned_phrases = self.evidence_validator.contains_banned_phrases(text)
                if banned_phrases:
                    self.logger.warning(
                        "Response contains banned phrases (possible hallucination): %s",
                        banned_phrases,
                    )
                    # Remove or replace banned phrases
                    for phrase_pattern in banned_phrases:
                        text = re.sub(
                            phrase_pattern,
                            "The document does not describe this.",
                            text,
                            flags=re.IGNORECASE,
                        )

                # Remove unexplained abbreviations (e.g., "HIV: R Non-Reactive" -> "HIV: Non-Reactive")
                text = re.sub(
                    r"\bHIV:\s*[A-Z]\s+Non-Reactive\b",
                    "HIV: Non-Reactive",
                    text,
                    flags=re.IGNORECASE,
                )
                text = re.sub(
                    r"\bHIV:\s*[A-Z]\s+Reactive\b",
                    "HIV: Reactive",
                    text,
                    flags=re.IGNORECASE,
                )

                # Fix "not tested" to gentler phrasing
                text = re.sub(
                    r"\bnot tested\b",
                    "not recorded / not done",
                    text,
                    flags=re.IGNORECASE,
                )

                # Ensure second person is used (replace "a patient's" with "your")
                text = re.sub(r"\ba patient\'?s\b", "your", text, flags=re.IGNORECASE)
                text = re.sub(r"\bthe patient\'?s\b", "your", text, flags=re.IGNORECASE)

                # Fix "an [X] checkup" -> "your [X] checkup"
                text = re.sub(
                    r"\ban\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+checkup\b",
                    r"your \1 checkup",
                    text,
                    flags=re.IGNORECASE,
                )
                text = re.sub(
                    r"\ban\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Profile\s+checkup\b",
                    r"your \1 checkup",
                    text,
                    flags=re.IGNORECASE,
                )
                # Also fix "summarizes an" -> "summarizes your"
                text = re.sub(
                    r"summarizes\s+an\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+checkup\b",
                    r"summarizes your \1 checkup",
                    text,
                    flags=re.IGNORECASE,
                )
                text = re.sub(
                    r"summarizes\s+an\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Profile\s+checkup\b",
                    r"summarizes your \1 checkup",
                    text,
                    flags=re.IGNORECASE,
                )

                # Fix contradiction: If both "TB Screening: Positive" and "Screening outcome: Negative" appear separately, combine them
                if re.search(
                    r"TB\s+Screening[:\s]+Positive", text, re.IGNORECASE
                ) and re.search(
                    r"Screening\s+outcome[:\s]+Negative", text, re.IGNORECASE
                ):
                    # Replace the separate lines with combined version
                    # First, remove the TB Screening line
                    text = re.sub(
                        r"\*\s*TB\s+Screening[:\s]+Positive\s*\n",
                        "",
                        text,
                        flags=re.IGNORECASE,
                    )
                    # Then replace the Screening outcome line with combined version
                    text = re.sub(
                        r"\*\s*Screening\s+outcome[:\s]+Negative\s*\n",
                        '* TB screening: Positive (the document also lists a screening outcome of "Negative"; please confirm with your clinic what this refers to)\n',
                        text,
                        flags=re.IGNORECASE,
                    )
                    # Also handle if they're on the same line or in different formats
                    text = re.sub(
                        r"\*\s*TB\s+Screening[:\s]+Positive[^\n]*\n\s*\*\s*Screening\s+outcome[:\s]+Negative",
                        '* TB screening: Positive (the document also lists a screening outcome of "Negative"; please confirm with your clinic what this refers to)',
                        text,
                        flags=re.IGNORECASE | re.MULTILINE,
                    )

                # Fix placeholder asterisks (****) in vital signs - LLM sometimes generates these when value is missing
                # Replace with explicit "not recorded" message
                text = re.sub(
                    r"\bpulse rate was recorded as\s+\*+\s+beats per minute",
                    "The document does not record your pulse rate.",
                    text,
                    flags=re.IGNORECASE,
                )
                text = re.sub(
                    r"\bpulse rate was\s+\*+\s+beats per minute",
                    "The document does not record your pulse rate.",
                    text,
                    flags=re.IGNORECASE,
                )
                text = re.sub(
                    r"\btemperature was recorded as\s+\*+\s*°c",
                    "The document does not record your temperature.",
                    text,
                    flags=re.IGNORECASE,
                )
                text = re.sub(
                    r"\bblood pressure was recorded as\s+\*+\s*mmhg",
                    "The document does not record your blood pressure.",
                    text,
                    flags=re.IGNORECASE,
                )

                # Remove any remaining placeholder patterns
                text = re.sub(
                    r"\b\w+\s+was\s+(recorded|measured|checked)\s+as\s+\*{2,}",
                    lambda m: f"The document does not record your {m.group(0).split()[0]}.",
                    text,
                    flags=re.IGNORECASE,
                )

                # Remove banned phrases that indicate inference without evidence
                banned_phrases = self.evidence_validator.contains_banned_phrases(text)
                if banned_phrases:
                    self.logger.warning(
                        "Response contains banned phrases (possible hallucination): %s",
                        banned_phrases,
                    )
                    # Remove or replace banned phrases
                    for phrase_pattern in banned_phrases:
                        text = re.sub(
                            phrase_pattern,
                            "The document does not describe this.",
                            text,
                            flags=re.IGNORECASE,
                        )

                # Drop any sentence that mentions bpm/mmHg/°C but contains no digits (prevents "measured at bpm" leaks).
                for unit in ["bpm", "mmhg", "°c"]:
                    if re.search(
                        rf"\b{re.escape(unit)}\b", text, flags=re.IGNORECASE
                    ) and not re.search(r"\d", text):
                        # If the entire response has no digits but mentions units, strip those sentences.
                        text = re.sub(
                            rf"[^.?!]*\b{re.escape(unit)}\b[^.?!]*[.?!]",
                            "",
                            text,
                            flags=re.IGNORECASE,
                        )

                text = re.sub(r"[ \t]+", " ", text)
                text = re.sub(r"\s*\n\s*", "\n", text).strip()
                text = self._enforce_numeric_grounding(
                    response_text=text,
                    context_text=latest_doc_text,
                    question=question,
                )
                stream_doc_sources_summary = [
                    {
                        "source_type": "document",
                        "source_id": latest_doc.id,
                        "relevance": 1.0,
                        "snippet_excerpt": latest_doc_text[:320]
                        + ("..." if len(latest_doc_text) > 320 else ""),
                    }
                ]
                text = self._append_numeric_claim_citations(
                    response_text=text,
                    sources_summary=stream_doc_sources_summary,
                )
                text = self._enforce_clinician_numeric_citations(
                    response_text=text,
                    question=question,
                    clinician_mode=clinician_mode,
                )

                if text:
                    self._set_stream_metadata(
                        num_sources=1,
                        sources_summary=stream_doc_sources_summary,
                    )
                    yield text
                    await self.conversation_manager.add_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=text,
                    )
                    return

        context_result = await self.context_engine.get_context(
            query=question,
            patient_id=patient_id,
            max_tokens=effective_max_context_tokens,
            system_prompt=enhanced_system_prompt,
            min_score=min_score,
        )
        self.logger.info(
            "RAG stream context built device=%s context_tokens=%s",
            device,
            effective_max_context_tokens,
        )
        decoding_profile = self._decoding_profile_for_query(
            question=question,
            routing=routing,
            context_result=context_result,
        )
        strict_violation, top_score = self._strict_grounding_violation(context_result)
        if strict_violation:
            if (
                top_score >= settings.llm_low_confidence_floor
                and context_result.synthesized_context.total_chunks_used > 0
            ):
                answer = self._build_low_confidence_inference(context_result)
                self._record_guardrail_event(
                    "strict_grounding_low_confidence",
                    mode="stream",
                )
            else:
                answer = self.STRICT_GROUNDING_REFUSAL
                self._record_guardrail_event(
                    "strict_grounding_no_evidence",
                    mode="stream",
                )
            sources_summary = self._build_sources_summary(context_result.ranked_results)
            self._set_stream_metadata(
                num_sources=context_result.synthesized_context.total_chunks_used,
                sources_summary=sources_summary,
            )
            self.logger.warning(
                "Strict grounding refusal (stream): patient=%s question=%s top_score=%.3f threshold=%.3f",
                patient_id,
                question,
                top_score,
                settings.llm_min_relevance_score,
            )
            yield answer
            await self.conversation_manager.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
            )
            return

        context_text = context_result.synthesized_context.full_context
        if not is_summary_query:
            can_answer, reason_if_no = self.evidence_validator.can_answer_from_context(
                question, context_text
            )
            if not can_answer:
                if question_mode == "GENERAL_MEDICAL":
                    reason_if_no = (
                        "The document does not explain this topic. "
                        "I can provide a general explanation if you'd like, "
                        "but it won't be from your medical records."
                    )
                    self._record_guardrail_event(
                        "general_medical_no_evidence",
                        mode="stream",
                    )
                else:
                    self._record_guardrail_event(
                        "evidence_gating_blocked",
                        mode="stream",
                    )
                answer = reason_if_no or "The document does not record this information."
                self.logger.warning(
                    "Evidence gating blocked stream answer: question=%s reason=%s",
                    question,
                    reason_if_no,
                )
                self._set_stream_metadata(
                    num_sources=context_result.synthesized_context.total_chunks_used,
                    sources_summary=self._build_sources_summary(
                        context_result.ranked_results
                    ),
                )
                yield answer
                await self.conversation_manager.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer,
                )
                return

        if not context_result.synthesized_context.total_chunks_used:
            # Mirror the diagnostic behaviour from ask() but in streaming form.
            self._set_stream_metadata(num_sources=0, sources_summary=[])
            if question_mode == "GENERAL_MEDICAL":
                answer = (
                    "The document does not explain this topic. "
                    "I can provide a general explanation if you'd like, "
                    "but it won't be from your medical records."
                )
                self._record_guardrail_event(
                    "general_medical_no_evidence",
                    mode="stream",
                )
                yield answer
                await self.conversation_manager.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer,
                )
                return
            result = await self.db.execute(
                select(func.count(MemoryChunk.id)).where(
                    MemoryChunk.patient_id == patient_id
                )
            )
            total_chunks = result.scalar() or 0

            result = await self.db.execute(
                select(func.count(MemoryChunk.id)).where(
                    MemoryChunk.patient_id == patient_id,
                    MemoryChunk.is_indexed.is_(True),
                )
            )
            indexed_chunks = result.scalar() or 0

            if total_chunks == 0:
                answer = (
                    "No relevant information could be retrieved because this patient "
                    "has no processed records or document chunks yet. "
                    "Upload and process documents or add structured data first."
                )
            elif indexed_chunks == 0:
                answer = (
                    "No relevant information could be retrieved. This patient has "
                    f"{total_chunks} document chunks, but none are indexed for semantic search. "
                    "This usually means embedding generation or indexing failed. "
                    "Reprocess the patient's documents or retry indexing."
                )
            else:
                answer = (
                    "No relevant information matching this question was found in the "
                    f"patient's indexed records (about {indexed_chunks} chunks). "
                    "Try rephrasing the question or checking that the relevant documents "
                    "have been uploaded and processed."
                )

            yield answer
            await self.conversation_manager.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
            )
            return

        direct_structured_answer = self._build_direct_structured_answer(
            question=question,
            context_result=context_result,
        )
        if direct_structured_answer:
            sources_summary = self._build_sources_summary(context_result.ranked_results)
            direct_structured_answer = self._append_numeric_claim_citations(
                response_text=direct_structured_answer,
                sources_summary=sources_summary,
            )
            self._record_guardrail_event("structured_direct", mode="stream")
            self._set_stream_metadata(
                num_sources=context_result.synthesized_context.total_chunks_used,
                sources_summary=sources_summary,
            )
            yield direct_structured_answer
            await self.conversation_manager.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=direct_structured_answer,
            )
            return

        # Clean up the prompt to remove section markers
        clean_prompt = context_result.prompt
        clean_prompt = clean_prompt.replace("--- 📄 Documents ---", "")
        clean_prompt = clean_prompt.replace("--- Documents ---", "")
        clean_prompt = clean_prompt.replace("--- 📝 Additional Notes ---", "")
        # Remove [Redacted] from context - but preserve actual medical data
        clean_prompt = re.sub(
            r"\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?", "", clean_prompt
        )
        if question_mode != "GENERAL_MEDICAL":
            few_shot_block = self._build_grounded_few_shot_block(
                context_result=context_result,
                clinician_mode=clinician_mode,
            )
            if few_shot_block:
                clean_prompt = f"{few_shot_block}\n\n{clean_prompt}"
        stream_sources_summary = self._build_sources_summary(context_result.ranked_results)
        self._set_stream_metadata(
            num_sources=context_result.synthesized_context.total_chunks_used,
            sources_summary=stream_sources_summary,
        )

        # Stream generation
        full_answer = ""
        yielded_chunks = False
        requires_buffered_validation = (
            clinician_mode
            or (
                settings.llm_strict_grounding
                and self._is_strict_grounding_intent(context_result)
            )
        )
        # MPS/CPU streaming can hang; strict factual queries also run buffered
        # so we can validate numeric grounding before any output is emitted.
        if device in ("mps", "cpu") or requires_buffered_validation:
            max_new_tokens = (
                min(settings.llm_max_new_tokens, 256)
                if device in ("mps", "cpu")
                else settings.llm_max_new_tokens
            )
            llm_response = await self.llm_service.generate(
                prompt=clean_prompt,
                max_new_tokens=max_new_tokens,
                temperature=decoding_profile.temperature,
                do_sample=decoding_profile.do_sample,
                top_p=decoding_profile.top_p,
                conversation_history=None,
            )
            full_answer = llm_response.text or ""
            if full_answer:
                full_answer = full_answer.replace("--- 📄 Documents ---", "")
                full_answer = full_answer.replace("--- Documents ---", "")
                full_answer = full_answer.replace("--- 📝 Additional Notes ---", "")
                full_answer = re.sub(
                    r"\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?", "", full_answer
                )
                full_answer = full_answer.replace("[Redacted]", "")
                full_answer = re.sub(
                    r"\[insert[^]]+here\]", "", full_answer, flags=re.IGNORECASE
                )
                full_answer = re.sub(r"\bof\s+bpm\b", "bpm", full_answer)
        else:
            async for chunk in self.llm_service.stream_generate(
                prompt=clean_prompt,
                system_prompt=None,  # Already in prompt
                temperature=decoding_profile.temperature,
                do_sample=decoding_profile.do_sample,
                top_p=decoding_profile.top_p,
            ):
                # Filter out section markers and placeholders as they stream
                cleaned_chunk = chunk
                if (
                    "--- 📄 Documents ---" in cleaned_chunk
                    or "--- Documents ---" in cleaned_chunk
                ):
                    cleaned_chunk = cleaned_chunk.replace("--- 📄 Documents ---", "")
                    cleaned_chunk = cleaned_chunk.replace("--- Documents ---", "")
                    cleaned_chunk = cleaned_chunk.replace(
                        "--- 📝 Additional Notes ---", ""
                    )
                # Remove [Redacted] and template-style placeholders in the streamed text
                cleaned_chunk = re.sub(
                    r"\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?", "", cleaned_chunk
                )
                cleaned_chunk = cleaned_chunk.replace("[Redacted]", "")
                cleaned_chunk = re.sub(r"(?i)\[insert[^]]+here\]", "", cleaned_chunk)
                cleaned_chunk = re.sub(
                    r"(?i)\[mention[^\]]*e\.g\.[^\]]+\]", "", cleaned_chunk
                )
                # Skip disclaimer chunks entirely
                if "disclaimer" in cleaned_chunk.lower():
                    continue
                if cleaned_chunk:
                    full_answer += cleaned_chunk
                    yielded_chunks = True
                    yield cleaned_chunk

        # Post-process to clean up any remaining artifacts
        full_answer = full_answer.replace("--- 📄 Documents ---", "")
        full_answer = full_answer.replace("--- Documents ---", "")
        full_answer = full_answer.replace("--- 📝 Additional Notes ---", "")

        # Remove [Redacted] placeholders more aggressively
        full_answer = re.sub(
            r"\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?", "", full_answer
        )
        full_answer = full_answer.replace("[Redacted]", "")

        # Remove template-style placeholders that indicate the model failed to fill in a value
        # Examples: "[Insert Pulse Rate Value Here]", "[mention specific test name, e.g., Cholesterol Panel]"
        full_answer = re.sub(r"(?i)\[insert[^]]+here\]", "", full_answer)
        full_answer = re.sub(r"(?i)\[mention[^\]]*e\.g\.[^\]]+\]", "", full_answer)
        # Clean up common leftover patterns like "of  bpm" (double space)
        full_answer = re.sub(r"\bof\s{2,}bpm\b", "bpm", full_answer)

        # Remove date patterns like "(2026-01-27)"
        full_answer = re.sub(r"\(\d{4}-\d{2}-\d{2}\)", "", full_answer)

        # Remove document structure artifacts - filter out lines that look like section headers
        lines = full_answer.split("\n")
        filtered_lines = []
        skip_section = False
        section_headers = [
            "dates and timestamps",
            "dates",
            "timestamps",
            "summary",
            "dates:",
            "timestamps:",
            "summary:",
            "next visit",
            "next visit:",
            "dates and timestamps:",
        ]

        for line in lines:
            stripped = line.strip()

            # Skip empty lines if we're in skip mode
            if skip_section and not stripped:
                continue

            # Skip section marker lines
            if stripped.startswith("---") and (
                "📄" in stripped or "Documents" in stripped or "Notes" in stripped
            ):
                skip_section = True
                continue

            # Skip section headers
            if any(header in stripped.lower() for header in section_headers):
                skip_section = True
                continue

            # Skip lines that are just date patterns or metadata
            if re.match(r"^\(?\d{4}-\d{2}-\d{2}\)?$", stripped):
                continue

            # Skip lines that are just "[Redacted]" or similar
            if re.match(r"^\[.*[Rr]edacted.*\]$", stripped):
                continue

            # End skip mode when we hit real content
            if skip_section and stripped:
                is_metadata = (
                    stripped.startswith("*")
                    or stripped.startswith("-")
                    or stripped.startswith("•")
                    or (stripped.startswith("(") and re.search(r"\d{4}", stripped))
                    or any(
                        keyword in stripped.lower()
                        for keyword in [
                            "date:",
                            "timestamp:",
                            "next visit:",
                            "redacted",
                        ]
                    )
                )
                if not is_metadata:
                    skip_section = False

            if not skip_section:
                filtered_lines.append(line)

        full_answer = "\n".join(filtered_lines).strip()

        # Remove trailing incomplete sentences
        lines = full_answer.split("\n")
        if lines:
            last_line = lines[-1].strip()
            if last_line.endswith(",") and len(last_line) < 50:
                lines = lines[:-1]
            full_answer = "\n".join(lines).strip()

        # Remove disclaimer-style boilerplate if the model still emits it
        disclaimer_patterns = [
            r"disclaimer.*intended for informational purposes only.*",
            r"always consult with your healthcare provider for personalized medical advice.*",
        ]
        for pat in disclaimer_patterns:
            full_answer = re.sub(pat, "", full_answer, flags=re.IGNORECASE | re.DOTALL)

        # Clean up multiple spaces and normalize whitespace
        full_answer = re.sub(r"[ \t]+", " ", full_answer)
        full_answer = re.sub(r"\s*\n\s*", "\n", full_answer).strip()
        full_answer = await self._self_correct_response(
            question=question,
            context_text=context_result.synthesized_context.full_context,
            response_text=full_answer,
            decoding_profile=decoding_profile,
        )
        full_answer = self._enforce_numeric_grounding(
            response_text=full_answer,
            context_text=context_result.synthesized_context.full_context,
            question=question,
        )
        full_answer = self._append_numeric_claim_citations(
            response_text=full_answer,
            sources_summary=stream_sources_summary,
        )
        full_answer = self._enforce_clinician_numeric_citations(
            response_text=full_answer,
            question=question,
            clinician_mode=clinician_mode,
        )
        if not full_answer:
            if clinician_mode:
                full_answer = self.CLINICIAN_CITATION_REFUSAL
            elif (
                settings.llm_strict_grounding
                and self._is_strict_grounding_intent(context_result)
            ):
                full_answer = self.STRICT_GROUNDING_REFUSAL
            else:
                full_answer = "The document does not record this information."

        if not yielded_chunks and full_answer:
            yield full_answer

        # Add assistant message
        await self.conversation_manager.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=full_answer,
        )

    async def continue_conversation(
        self,
        conversation_id: UUID,
        question: str,
        system_prompt: str | None = None,
        max_context_tokens: int = 4000,
    ) -> RAGResponse:
        """Continue an existing conversation.

        Args:
            conversation_id: Existing conversation ID
            question: New question
            system_prompt: Override system prompt
            max_context_tokens: Maximum context tokens

        Returns:
            RAGResponse with answer
        """
        # Get conversation
        conversation = await self.conversation_manager.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        return await self.ask(
            question=question,
            patient_id=conversation.patient_id,
            conversation_id=conversation_id,
            system_prompt=system_prompt,
            max_context_tokens=max_context_tokens,
            use_conversation_history=True,
        )

    async def ask_structured(
        self,
        question: str,
        patient_id: int,
        conversation_id: UUID | None = None,
        system_prompt: str | None = None,
        max_context_tokens: int = 4000,
        use_conversation_history: bool = True,
    ) -> tuple[RAGResponse, StructuredSummaryResponse | None]:
        """Ask with structured JSON output.

        Returns both the RAGResponse and parsed structured data.

        Args:
            question: User's question
            patient_id: Patient ID
            conversation_id: Optional existing conversation ID
            system_prompt: Override system prompt
            max_context_tokens: Maximum tokens for context
            use_conversation_history: Include conversation history in prompt

        Returns:
            Tuple of (RAGResponse, Optional[StructuredSummaryResponse])
        """
        import json
        import time

        total_start = time.time()

        # Get or create conversation
        if conversation_id:
            conversation = await self.conversation_manager.get_conversation(
                conversation_id
            )
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = await self.conversation_manager.create_conversation(
                patient_id
            )
            conversation_id = conversation.conversation_id

        # Add user message
        await self.conversation_manager.add_message(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )

        routing = self.query_router.route(question)
        wants_latest_doc = (
            routing.task == QueryTask.DOC_SUMMARY
            and routing.temporal_intent == "latest"
        )
        clinician_mode = self._is_clinician_mode(system_prompt)
        context_text = ""
        sources_summary: list[dict] = []
        context_time_ms = 0.0
        context_result = None

        async def _structured_refusal(
            *,
            finish_reason: str,
            message: str | None = None,
        ) -> tuple[RAGResponse, StructuredSummaryResponse | None]:
            refusal = (
                message
                or (
                    self.CLINICIAN_CITATION_REFUSAL
                    if clinician_mode
                    else self.STRICT_GROUNDING_REFUSAL
                )
            )
            assistant_message = await self.conversation_manager.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=refusal,
            )
            total_time = (time.time() - total_start) * 1000
            refusal_response = RAGResponse(
                answer=refusal,
                llm_response=LLMResponse(
                    text=refusal,
                    tokens_generated=0,
                    tokens_input=0,
                    generation_time_ms=0.0,
                    finish_reason=finish_reason,
                ),
                context_used=context_text[:500] + "..."
                if len(context_text) > 500
                else context_text,
                num_sources=len(sources_summary),
                sources_summary=sources_summary,
                conversation_id=conversation_id,
                message_id=assistant_message.message_id,
                context_time_ms=context_time_ms,
                generation_time_ms=0.0,
                total_time_ms=total_time,
            )
            return refusal_response, None

        context_start = time.time()
        latest_doc: Document | None = None
        latest_doc_text: str | None = None
        if wants_latest_doc and self.db is not None:
            latest_doc_result = await self.db.execute(
                select(Document)
                .where(
                    Document.patient_id == patient_id,
                    Document.processing_status == "completed",
                    Document.extracted_text.is_not(None),
                )
                .order_by(Document.received_date.desc())
                .limit(1)
            )
            latest_doc = latest_doc_result.scalar_one_or_none()
            if (
                latest_doc
                and latest_doc.extracted_text
                and latest_doc.extracted_text.strip()
            ):
                latest_doc_text = latest_doc.extracted_text.strip()
                sources_summary = [
                    {
                        "source_type": "document",
                        "source_id": latest_doc.id,
                        "relevance": 1.0,
                        "snippet_excerpt": latest_doc_text[:320]
                        + ("..." if len(latest_doc_text) > 320 else ""),
                    }
                ]
                context_text = latest_doc_text

        if not context_text:
            context_result = await self.context_engine.get_context(
                query=question,
                patient_id=patient_id,
                max_tokens=max_context_tokens,
                system_prompt=system_prompt or self.DEFAULT_SYSTEM_PROMPT,
                min_score=0.2,
            )
            sources_summary = self._build_sources_summary(
                getattr(context_result, "ranked_results", []),
            )
            synthesized = getattr(context_result, "synthesized_context", None)
            context_text = (
                (getattr(synthesized, "full_context", "") or "").strip()
                if synthesized is not None
                else ""
            )
            has_evidence = bool(
                context_text and getattr(synthesized, "total_chunks_used", 0) > 0
            )
            if not has_evidence:
                self._record_guardrail_event("structured_no_evidence")
                return await _structured_refusal(finish_reason="structured_no_evidence")

            strict_violation, _top_score = self._strict_grounding_violation(context_result)
            if strict_violation:
                self._record_guardrail_event("structured_strict_grounding_refusal")
                return await _structured_refusal(
                    finish_reason="strict_grounding_no_evidence"
                )

        context_time_ms = (time.time() - context_start) * 1000

        # Build JSON prompt with grounded evidence context

        json_prompt = (
            "You must respond with VALID JSON only. The JSON must start with '{' and end with '}'. "
            "No markdown, no code fences, no commentary before or after the JSON.\n\n"
            "JSON Schema:\n"
            "{\n"
            '  "overview": "One-sentence friendly overview",\n'
            '  "key_results": [\n'
            '    {"name": "Lab name", "value": "10.1", "value_num": 10.1, "unit": "g/dL", "date": "2026-01-27", "is_normal": true, "source_snippet": "exact text from document"},\n'
            '    {"name": "HIV Test", "value": "Negative", "value_num": null, "unit": null, "date": "2026-01-27", "is_normal": true, "source_snippet": "HIV: R Non-Reactive"},\n'
            "    ...\n"
            "  ],\n"
            '  "medications": [\n'
            '    {"name": "Med name", "dosage": "500mg", "frequency": "twice daily", "source_snippet": "exact text from document"},\n'
            "    ...\n"
            "  ],\n"
            '  "vital_signs": {"pulse": "72 bpm", "blood_pressure": "120/80 mmHg", "temperature": "37.0°C"},\n'
            '  "follow_ups": ["Action 1", "Action 2"],\n'
            '  "concerns": ["Concern 1"],\n'
            '  "source_document_id": 123,\n'
            '  "extraction_date": "2026-01-27"\n'
            "}\n\n"
            "CRITICAL RULES:\n"
            "- value must be a STRING (e.g., '10.1', 'Negative', '<0.1', 'O+', 'POS')\n"
            "- value_num is optional float if value is numeric (for sorting)\n"
            "- source_snippet is REQUIRED for every key_result and medication (exact text from document)\n"
            "- Include ONLY numbers/values that appear in the document\n"
            "- If a value is missing, use null (not a placeholder)\n"
            "- Dates must be in YYYY-MM-DD format\n\n"
            f"DOCUMENT TEXT:\n{context_text}\n\n"
            f"Question: {question}\n\n"
            "JSON Response (must start with '{'):"
        )

        # Generate with retry on invalid JSON
        max_retries = 2
        structured = None
        for attempt in range(max_retries):
            device = getattr(self.llm_service, "device", None) or "cpu"
            max_new_tokens = settings.llm_max_new_tokens
            if device in ("mps", "cpu"):
                max_new_tokens = min(settings.llm_max_new_tokens, 512)

            llm_response = await self.llm_service.generate(
                prompt=json_prompt,
                system_prompt="You are a medical data extraction assistant. Return ONLY valid JSON.",
                max_new_tokens=max_new_tokens,
            )

            # Extract JSON from response (handle markdown code fences and preamble)
            text = llm_response.text.strip()

            # Remove markdown code fences
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            # Extract first {...} block if there's preamble (common with LLMs)
            if not text.startswith("{"):
                start = text.find("{")
                end = text.rfind("}") + 1
                if start != -1 and end > start:
                    text = text[start:end]

            try:
                data = json.loads(text)

                # Validate structured response
                structured = StructuredSummaryResponse(**data)

                # Response validator: check that all numbers have source snippets
                validation_errors = self._validate_structured_response(
                    structured, context_text
                )
                if validation_errors:
                    if attempt < max_retries - 1:
                        self.logger.warning(
                            "Validation failed on attempt %d: %s",
                            attempt + 1,
                            validation_errors,
                        )
                        json_prompt = (
                            f"The previous response had validation errors: {validation_errors}. "
                            "Every value must have a source_snippet showing where it came from in the document. "
                            "Do not invent values. Return ONLY valid JSON.\n\n"
                            + json_prompt
                        )
                        continue
                    else:
                        self.logger.error(
                            "Validation failed after all retries: %s", validation_errors
                        )
                        self._record_guardrail_event(
                            "structured_validation_refusal",
                            errors=len(validation_errors),
                        )
                        return await _structured_refusal(
                            finish_reason="structured_validation_failed"
                        )

                break
            except (json.JSONDecodeError, ValueError) as e:
                if attempt < max_retries - 1:
                    self.logger.warning(
                        "Invalid JSON on attempt %d, retrying: %s", attempt + 1, e
                    )
                    json_prompt = (
                        "The previous response was invalid JSON. Return ONLY valid JSON, no markdown, no code fences.\n\n"
                        + json_prompt
                    )
                else:
                    self.logger.error(
                        "Failed to get valid JSON after %d attempts", max_retries
                    )
                    self._record_guardrail_event(
                        "structured_invalid_json_refusal",
                    )
                    return await _structured_refusal(
                        finish_reason="structured_invalid_json"
                    )

        if structured is None:
            self._record_guardrail_event("structured_empty_refusal")
            return await _structured_refusal(finish_reason="structured_empty")

        # Convert structured to friendly text
        friendly_text = (
            self._structured_to_friendly(structured)
            if structured
            else llm_response.text
        )

        # Add assistant message
        assistant_message = await self.conversation_manager.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=friendly_text,
        )

        total_time = (time.time() - total_start) * 1000

        rag_response = RAGResponse(
            answer=friendly_text,
            llm_response=llm_response,
            context_used=context_text[:500] + "..."
            if len(context_text) > 500
            else context_text,
            num_sources=len(sources_summary),
            sources_summary=sources_summary,
            conversation_id=conversation_id,
            message_id=assistant_message.message_id,
            context_time_ms=context_time_ms,
            generation_time_ms=llm_response.generation_time_ms,
            total_time_ms=total_time,
        )

        return rag_response, structured

    def _build_direct_structured_answer(
        self,
        *,
        question: str,
        context_result,
    ) -> str | None:
        """Build a deterministic answer from structured retrieval hits.

        This path avoids unnecessary LLM generation for straightforward factual
        queries and reduces hallucination risk.
        """
        query_analysis = getattr(context_result, "query_analysis", None)
        intent = getattr(query_analysis, "intent", None)
        question_lower = question.lower()
        requested_tests = [
            t.lower() for t in getattr(query_analysis, "test_names", []) if t
        ]

        is_trend_query = any(
            token in question_lower
            for token in [
                "trend",
                "over time",
                "changed",
                "improved",
                "worsened",
                "increase",
                "decrease",
            ]
        )

        is_simple_fact_query = intent in {
            QueryIntent.LIST,
            QueryIntent.VALUE,
            QueryIntent.STATUS,
        }
        if not is_simple_fact_query:
            is_simple_fact_query = any(
                token in question_lower
                for token in [
                    "medication",
                    "medications",
                    "meds",
                    "drug",
                    "drugs",
                    "taking",
                ]
            ) or bool(requested_tests)

        if not is_simple_fact_query:
            return None

        ranked_results = getattr(context_result, "ranked_results", []) or []
        structured_results = [
            r
            for r in ranked_results
            if getattr(r.result, "source_type", None) in {"lab_result", "medication"}
        ]
        if not structured_results:
            return None

        if is_trend_query:
            return self._build_direct_trend_answer(
                structured_results=structured_results,
                requested_tests=requested_tests,
            )

        medication_query = any(
            token in question_lower
            for token in ["medication", "medications", "meds", "drug", "taking"]
        )
        if medication_query:
            med_lines = []
            for ranked in structured_results:
                if ranked.result.source_type != "medication":
                    continue
                line = self._normalize_structured_content(ranked.result.content)
                if line:
                    med_lines.append(line)
            med_lines = list(dict.fromkeys(med_lines))
            if not med_lines:
                return "The document does not record this information."
            if len(med_lines) == 1:
                return f"From your records, your active medication is: {med_lines[0]}"
            bullets = "\n".join(f"- {line}" for line in med_lines[:8])
            return f"From your records, your active medications are:\n{bullets}"

        # Default factual response from lab/med retrieval lines.
        fact_lines = []
        for ranked in structured_results:
            line = self._normalize_structured_content(ranked.result.content)
            if not line:
                continue
            if ranked.result.source_type == "lab_result" and requested_tests:
                line_lower = line.lower()
                if not any(test in line_lower for test in requested_tests):
                    continue
            fact_lines.append(line)

        if not fact_lines:
            return None

        fact_lines = list(dict.fromkeys(fact_lines))
        if len(fact_lines) == 1:
            return f"From your records: {fact_lines[0]}"
        bullets = "\n".join(f"- {line}" for line in fact_lines[:8])
        return f"From your records:\n{bullets}"

    def _build_direct_trend_answer(
        self,
        *,
        structured_results: list,
        requested_tests: list[str],
    ) -> str:
        """Build deterministic trend answer from dated structured lab values."""

        trend_points: list[dict] = []
        for ranked in structured_results:
            if getattr(ranked.result, "source_type", None) != "lab_result":
                continue

            context_date = getattr(ranked.result, "context_date", None)
            if context_date is None:
                continue

            line = self._normalize_structured_content(ranked.result.content)
            if not line:
                continue
            line_lower = line.lower()
            if requested_tests and not any(test in line_lower for test in requested_tests):
                continue

            parsed = self._extract_trend_value(line)
            if parsed is None:
                continue
            name, value, unit, value_type = parsed
            trend_points.append(
                {
                    "name": name,
                    "value": value,
                    "unit": unit,
                    "value_type": value_type,
                    "date": context_date,
                }
            )

        if not trend_points:
            return "From your records, there are not enough dated values to determine a trend."

        if not requested_tests:
            distinct_names = {p["name"].lower() for p in trend_points}
            if len(distinct_names) > 1:
                return "From your records, please specify which test trend you want to review."

        trend_points.sort(key=lambda p: p["date"])
        selected_name = (
            trend_points[-1]["name"] if trend_points else "the requested lab value"
        )
        selected_points = [
            p for p in trend_points if p["name"].lower() == selected_name.lower()
        ]
        if len(selected_points) < 2:
            selected_points = trend_points

        if len(selected_points) < 2:
            return "From your records, there are not enough dated values to determine a trend."

        value_type = selected_points[0]["value_type"]
        if any(p["value_type"] != value_type for p in selected_points):
            return "From your records, there are not enough consistent values to determine a trend."

        first = selected_points[0]
        last = selected_points[-1]
        unit = first["unit"] or last["unit"] or ""
        unit_suffix = f" {unit}" if unit else ""
        first_date = self._format_context_date(first["date"])
        last_date = self._format_context_date(last["date"])

        if value_type == "numeric":
            first_value = self._format_numeric_value(first["value"])
            last_value = self._format_numeric_value(last["value"])
            delta = float(last["value"]) - float(first["value"])

            if abs(delta) < 1e-9:
                trend_phrase = "stayed about the same"
            else:
                delta_text = self._format_numeric_value(abs(delta))
                direction = "increased" if delta > 0 else "decreased"
                trend_phrase = f"{direction} by {delta_text}{unit_suffix}"

            return (
                f"From your records, {selected_name} changed from "
                f"{first_value}{unit_suffix} on {first_date} to "
                f"{last_value}{unit_suffix} on {last_date} ({trend_phrase})."
            )

        if value_type == "ratio":
            first_value = f"{first['value'][0]}/{first['value'][1]}"
            last_value = f"{last['value'][0]}/{last['value'][1]}"
            systolic_delta = last["value"][0] - first["value"][0]
            diastolic_delta = last["value"][1] - first["value"][1]
            if systolic_delta == 0 and diastolic_delta == 0:
                trend_phrase = "stayed about the same"
            else:
                systolic_phrase = self._format_delta_phrase(
                    systolic_delta,
                    "systolic",
                    unit_suffix,
                )
                diastolic_phrase = self._format_delta_phrase(
                    diastolic_delta,
                    "diastolic",
                    unit_suffix,
                )
                trend_phrase = ", ".join(
                    phrase for phrase in [systolic_phrase, diastolic_phrase] if phrase
                )
            return (
                f"From your records, {selected_name} changed from "
                f"{first_value}{unit_suffix} on {first_date} to "
                f"{last_value}{unit_suffix} on {last_date} ({trend_phrase})."
            )

        if value_type == "categorical":
            first_value = str(first["value"])
            last_value = str(last["value"])
            if first_value.lower() == last_value.lower():
                trend_phrase = "stayed the same"
            else:
                trend_phrase = f"changed from {first_value} to {last_value}"
            return (
                f"From your records, {selected_name} {trend_phrase} "
                f"between {first_date} and {last_date}."
            )

        return "From your records, there are not enough dated values to determine a trend."

    def _extract_trend_value(
        self, line: str
    ) -> tuple[str, object, str | None, str] | None:
        """Extract trend value from structured lines."""
        match_ratio = re.search(
            r"^(?P<name>[^:]+):\s*(?P<sys>\d{2,3})\s*/\s*(?P<dia>\d{2,3})\s*(?P<unit>[a-zA-Z/%°]+)?",
            line,
        )
        if match_ratio:
            name = match_ratio.group("name").strip()
            unit = (match_ratio.group("unit") or "").strip() or None
            if not name:
                return None
            return (
                name,
                (int(match_ratio.group("sys")), int(match_ratio.group("dia"))),
                unit,
                "ratio",
            )

        match_numeric = re.search(
            r"^(?P<name>[^:]+):\s*(?P<value>[-+]?\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Z/%°]+)?",
            line,
        )
        if match_numeric:
            name = match_numeric.group("name").strip()
            try:
                value = float(match_numeric.group("value"))
            except (TypeError, ValueError):
                value = None
            unit = (match_numeric.group("unit") or "").strip() or None
            if not name or value is None:
                return None
            return name, value, unit, "numeric"

        match_category = re.search(
            r"^(?P<name>[^:]+):\s*(?P<value>non-?reactive|reactive|positive|negative|detected|not detected|indeterminate)\b",
            line,
            flags=re.IGNORECASE,
        )
        if match_category:
            name = match_category.group("name").strip()
            value = match_category.group("value").strip().title()
            if not name:
                return None
            return name, value, None, "categorical"

        return None

    @staticmethod
    def _format_delta_phrase(delta: int, label: str, unit_suffix: str) -> str:
        if delta == 0:
            return ""
        direction = "increased" if delta > 0 else "decreased"
        return f"{label} {direction} by {abs(delta)}{unit_suffix}"

    @staticmethod
    def _format_numeric_value(value: float) -> str:
        """Format numeric values for user-friendly deterministic answers."""
        if float(value).is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_context_date(value) -> str:
        """Format datetime/date-like values as YYYY-MM-DD."""
        if hasattr(value, "date"):
            try:
                return value.date().isoformat()
            except Exception:
                pass
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        return str(value)

    def _normalize_structured_content(self, content: str) -> str:
        """Normalize structured retrieval snippets for direct user answers."""
        text = (content or "").strip()
        if not text:
            return ""
        text = re.sub(r"^\s*Lab:\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^\s*Medication:\s*", "", text, flags=re.IGNORECASE)
        text = text.replace(" = ", ": ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _validate_structured_response(
        self,
        structured: StructuredSummaryResponse,
        context_text: str,
    ) -> list[str]:
        """Validate structured response for safety and grounding.

        Checks:
        1. Every key_result has a source_snippet
        2. Every medication has a source_snippet
        3. All values appear in context_text (basic check)
        4. No invented numbers without sources

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        context_lower = context_text.lower()

        # Check key_results
        for i, result in enumerate(structured.key_results):
            if not result.source_snippet or not result.source_snippet.strip():
                errors.append(f"key_results[{i}].{result.name} missing source_snippet")
            elif result.value:
                # Check if value appears in context (basic grounding check)
                value_lower = str(result.value).lower()
                snippet_lower = result.source_snippet.lower()
                if (
                    value_lower not in snippet_lower
                    and value_lower not in context_lower
                ):
                    errors.append(
                        f"key_results[{i}].{result.name} value '{result.value}' not found in source_snippet or context"
                    )

        # Check medications
        for i, med in enumerate(structured.medications):
            if not med.source_snippet or not med.source_snippet.strip():
                errors.append(f"medications[{i}].{med.name} missing source_snippet")

        return errors

    def _structured_to_friendly(self, structured: StructuredSummaryResponse) -> str:
        """Convert structured response to friendly text for display."""
        lines = [f"**✅ Overview**\n{structured.overview}\n"]

        if structured.key_results:
            lines.append("**📋 Key Results**")
            for result in structured.key_results:
                # Use value (string) with unit
                value_str = result.value or "N/A"
                if result.unit:
                    value_str = f"{value_str} {result.unit}"
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
