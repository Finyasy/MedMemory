"""RAG service: context retrieval + LLM generation for medical Q&A."""

from dataclasses import dataclass
import logging
import re
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import MemoryChunk
from app.models.document import Document
from app.models.patient import Patient
from app.services.context import ContextEngine
from app.services.llm.conversation import Conversation, ConversationManager
from app.services.llm.model import LLMService, LLMResponse
from app.services.llm.query_router import QueryRouter, QueryTask
from app.services.llm.evidence_validator import EvidenceValidator
from app.schemas.chat import StructuredSummaryResponse


@dataclass
class RAGResponse:
    """Response from RAG service."""
    answer: str
    llm_response: LLMResponse
    context_used: str
    num_sources: int
    sources_summary: list[dict]
    conversation_id: UUID
    message_id: Optional[int] = None
    context_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    total_time_ms: float = 0.0


class RAGService:
    """RAG: context retrieval, prompt build, LLM generation, conversation storage."""

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

    def __init__(
        self,
        db: AsyncSession,
        llm_service: Optional[LLMService] = None,
        context_engine: Optional[ContextEngine] = None,
        conversation_manager: Optional[ConversationManager] = None,
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
        self.evidence_validator = EvidenceValidator()
        self.logger = logging.getLogger("medmemory")

    async def ask(
        self,
        question: str,
        patient_id: int,
        conversation_id: Optional[UUID] = None,
        system_prompt: Optional[str] = None,
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
            conversation = await self.conversation_manager.get_conversation(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = await self.conversation_manager.create_conversation(patient_id)
            conversation_id = conversation.conversation_id
        self.logger.info("ASK start patient=%s conv=%s", patient_id, conversation_id)

        # Fetch patient information for personalized greeting
        patient_result = await self.db.execute(
            select(Patient).where(Patient.id == patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        patient_first_name = patient.first_name if patient else None

        # Add user message
        user_message = await self.conversation_manager.add_message(
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
        
        # Check if question is general medical knowledge (not record-based)
        question_mode = self.evidence_validator.detect_question_mode(question)
        if question_mode == 'GENERAL_MEDICAL':
            # For general knowledge questions, check if we should answer from records first
            # If not in records, ask permission to provide general explanation
            self.logger.info("Question detected as GENERAL_MEDICAL, will check records first")
        
        context_start = time.time()
        device = getattr(self.llm_service, "device", None)
        if not device:
            device = "cuda" if hasattr(self.llm_service, "stream_generate") else "cpu"
        effective_max_context_tokens = max_context_tokens
        if device in ("mps", "cpu"):
            effective_max_context_tokens = min(max_context_tokens, 2000)

        min_score = 0.3
        enhanced_system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

        is_summary_query = routing.task == QueryTask.DOC_SUMMARY or any(keyword in question.lower() for keyword in ['summarize', 'summary', 'overview', 'findings', 'key information', 'clear', 'easy-to-understand'])
        is_document_query = routing.task == QueryTask.VISION_EXTRACTION or any(keyword in question.lower() for keyword in ['document', 'image', 'picture', 'photo', 'scan', 'report', 'what does', 'what is in', 'what information'])

        if is_summary_query or is_document_query:
            min_score = 0.2

        wants_latest_doc_summary = (
            is_summary_query
            and any(
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
            if latest_doc and latest_doc.extracted_text and latest_doc.extracted_text.strip():
                latest_doc_text = latest_doc.extracted_text.strip()
                
                text_confidence = getattr(latest_doc, 'extraction_confidence', 1.0)
                text_length = len(latest_doc_text.strip())
                use_vision = (
                    text_length < 200 or
                    text_confidence < 0.7 or
                    "image" in question.lower() or
                    "picture" in question.lower() or
                    routing.task == QueryTask.VISION_EXTRACTION
                )
                
                if use_vision and hasattr(latest_doc, 'file_path') and latest_doc.file_path:
                    try:
                        from pathlib import Path
                        import fitz
                        
                        doc_path = Path(latest_doc.file_path)
                        if doc_path.exists():
                            img_bytes = None
                            
                            if doc_path.suffix.lower() == '.pdf':
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
                                    vision_text = vision_text.split("```json")[1].split("```")[0].strip()
                                elif "```" in vision_text:
                                    vision_text = vision_text.split("```")[1].split("```")[0].strip()
                                
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
                                            structured_parts.append(f"{lv.get('name', '')}: {val_str}")
                                    if vision_data.get("vital_signs"):
                                        for k, v in vision_data["vital_signs"].items():
                                            if v:
                                                structured_parts.append(f"{k}: {v}")
                                    if vision_data.get("raw_extraction"):
                                        structured_parts.append(vision_data["raw_extraction"])
                                    
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
                                    self.logger.warning("Vision extraction JSON parse failed, using free text")
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
                latest_doc_text[:200] + "..." if len(latest_doc_text) > 200 else latest_doc_text,
            )

            greeting = f"Hi {patient_first_name}," if patient_first_name else "Hi there,"
            
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
                "- Do NOT add meta text like \"I understand\" or \"Here is the summary\".\n"
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
                system_prompt=enhanced_system_prompt,
                conversation_history=conversation_history,
            )
            generation_time = (time.time() - generation_start) * 1000

            cleaned_response_text = llm_response.text
            
            is_summary_query = any(keyword in question.lower() for keyword in ['summarize', 'summary', 'overview', 'findings'])
            
            if is_summary_query:
                if len(cleaned_response_text.strip()) < 10:
                    self.logger.warning("Summary response suspiciously short: %s", cleaned_response_text[:50])
            else:
                is_valid, validation_error = self.evidence_validator.validate_response(
                    cleaned_response_text,
                    latest_doc_text,
                    question
                )
                
                if not is_valid and validation_error:
                    self.logger.warning(
                        "Response validation failed (direct summary): question=%s error=%s",
                        question,
                        validation_error
                    )
                    cleaned_response_text = validation_error
            
            banned_phrases = self.evidence_validator.contains_banned_phrases(cleaned_response_text)
            if banned_phrases:
                self.logger.warning("Response contains banned phrases (possible hallucination): %s", banned_phrases)
                for phrase_pattern in banned_phrases:
                    cleaned_response_text = re.sub(
                        phrase_pattern,
                        "The document does not describe this.",
                        cleaned_response_text,
                        flags=re.IGNORECASE,
                    )

            if patient_first_name:
                if not re.match(rf'^\s*Hi\s+{re.escape(patient_first_name)}', cleaned_response_text, re.IGNORECASE):
                    if re.match(r'^\s*Hi\s+', cleaned_response_text, re.IGNORECASE):
                        cleaned_response_text = re.sub(
                            r'^\s*Hi\s+[^,\n]+',
                            f'Hi {patient_first_name}',
                            cleaned_response_text,
                            flags=re.IGNORECASE
                        )
                    else:
                        cleaned_response_text = f"Hi {patient_first_name},\n\n{cleaned_response_text.lstrip()}"
            elif not re.match(r'^\s*Hi\s+', cleaned_response_text, re.IGNORECASE):
                cleaned_response_text = f"Hi there,\n\n{cleaned_response_text.lstrip()}"
            
            cleaned_response_text = re.sub(
                r'(?is)^\s*(i understand[^.\n]*\.\s*)+',
                '',
                cleaned_response_text or "",
            )
            cleaned_response_text = re.sub(
                r'(?im)^\s*here is the summary:\s*',
                '',
                cleaned_response_text,
            ).lstrip()
            
            ocr_fixes = {
                r'\bUrineysis\b': 'Urinalysis',
                r'\bIsolazid\b': 'Isoniazid',
                r'\bNR\b(?!\s*[A-Z])': 'not recorded',
                r'\bNR\s+Not\s+tested\b': 'not recorded / not done',
            }
            for pattern, replacement in ocr_fixes.items():
                cleaned_response_text = re.sub(pattern, replacement, cleaned_response_text, flags=re.IGNORECASE)
            
            cleaned_response_text = re.sub(
                r'\bHIV:\s*[A-Z]\s+Non-Reactive\b',
                'HIV: Non-Reactive',
                cleaned_response_text,
                flags=re.IGNORECASE
            )
            cleaned_response_text = re.sub(
                r'\bHIV:\s*[A-Z]\s+Reactive\b',
                'HIV: Reactive',
                cleaned_response_text,
                flags=re.IGNORECASE
            )
            
            cleaned_response_text = re.sub(
                r'\bnot tested\b',
                'not recorded / not done',
                cleaned_response_text,
                flags=re.IGNORECASE
            )
            
            cleaned_response_text = re.sub(
                r'\ba patient\'?s\b',
                'your',
                cleaned_response_text,
                flags=re.IGNORECASE
            )
            cleaned_response_text = re.sub(
                r'\bthe patient\'?s\b',
                'your',
                cleaned_response_text,
                flags=re.IGNORECASE
            )
            
            cleaned_response_text = re.sub(
                r'\ban\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+checkup\b',
                r'your \1 checkup',
                cleaned_response_text,
                flags=re.IGNORECASE
            )
            cleaned_response_text = re.sub(
                r'\ban\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Profile\s+checkup\b',
                r'your \1 checkup',
                cleaned_response_text,
                flags=re.IGNORECASE
            )
            cleaned_response_text = re.sub(
                r'summarizes\s+an\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+checkup\b',
                r'summarizes your \1 checkup',
                cleaned_response_text,
                flags=re.IGNORECASE
            )
            cleaned_response_text = re.sub(
                r'summarizes\s+an\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Profile\s+checkup\b',
                r'summarizes your \1 checkup',
                cleaned_response_text,
                flags=re.IGNORECASE
            )
            
            if re.search(r'TB\s+Screening[:\s]+Positive', cleaned_response_text, re.IGNORECASE) and \
               re.search(r'Screening\s+outcome[:\s]+Negative', cleaned_response_text, re.IGNORECASE):
                cleaned_response_text = re.sub(
                    r'\*\s*TB\s+Screening[:\s]+Positive\s*\n',
                    '',
                    cleaned_response_text,
                    flags=re.IGNORECASE
                )
                cleaned_response_text = re.sub(
                    r'\*\s*Screening\s+outcome[:\s]+Negative\s*\n',
                    '* TB screening: Positive (the document also lists a screening outcome of "Negative"; please confirm with your clinic what this refers to)\n',
                    cleaned_response_text,
                    flags=re.IGNORECASE
                )
                cleaned_response_text = re.sub(
                    r'\*\s*TB\s+Screening[:\s]+Positive[^\n]*\n\s*\*\s*Screening\s+outcome[:\s]+Negative',
                    '* TB screening: Positive (the document also lists a screening outcome of "Negative"; please confirm with your clinic what this refers to)',
                    cleaned_response_text,
                    flags=re.IGNORECASE | re.MULTILINE
                )
            
            # Remove banned phrases that indicate inference without evidence
            banned_phrases = self.evidence_validator.contains_banned_phrases(cleaned_response_text)
            if banned_phrases:
                self.logger.warning("Response contains banned phrases (possible hallucination): %s", banned_phrases)
                # Remove or replace banned phrases
                for phrase_pattern in banned_phrases:
                    cleaned_response_text = re.sub(
                        phrase_pattern,
                        "The document does not describe this.",
                        cleaned_response_text,
                        flags=re.IGNORECASE,
                    )
            
            hallucination_patterns = [
                (r'further\s+testing\s+confirmed', 'The document does not state this.'),
                (r'normal\s+findings\s+during\s+the\s+examination', 'The document does not describe the examination findings.'),
                (r'your\s+doctor\s+will\s+review\s+this\s+result', ''),
                (r'your\s+doctor\s+will\s+provide\s+more\s+detailed\s+explanations', ''),
                (r'to\s+determine\s+if\s+it\s+needs\s+further\s+investigation', ''),
                (r'this\s+is\s+within\s+the\s+typical\s+range', ''),
                (r'this\s+is\s+within\s+the\s+normal\s+range', ''),
                (r'performed\s+on\s+January\s+\d{1,2}(?:st|nd|rd|th)?,\s+2026', ''),
                (r'performed\s+on\s+\w+\s+\d{1,2}(?:st|nd|rd|th)?,\s+2026', ''),
            ]
            for pattern, replacement in hallucination_patterns:
                cleaned_response_text = re.sub(pattern, replacement, cleaned_response_text, flags=re.IGNORECASE)
            cleaned_response_text = cleaned_response_text.replace("--- 📄 Documents ---", "")
            cleaned_response_text = cleaned_response_text.replace("--- Documents ---", "")
            cleaned_response_text = cleaned_response_text.replace("--- 📝 Additional Notes ---", "")

            # Remove [Redacted] placeholders more aggressively
            cleaned_response_text = re.sub(r'\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?', '', cleaned_response_text)
            cleaned_response_text = cleaned_response_text.replace("[Redacted]", "")

            # Remove template-style placeholders (but only if they're actual placeholders, not real values)
            cleaned_response_text = re.sub(r'(?i)\[insert[^]]+here\]', '', cleaned_response_text)
            cleaned_response_text = re.sub(r'(?i)\[mention[^\]]*e\.g\.[^\]]+\]', '', cleaned_response_text)
            
            # Remove specific placeholder patterns like [Pulse Rate Value], [Value], etc.
            cleaned_response_text = re.sub(r'\[[^\]]*[Vv]alue[^\]]*\]', 'The document does not record this information.', cleaned_response_text)
            cleaned_response_text = re.sub(r'\[[^\]]*[Pp]ulse[^\]]*[Rr]ate[^\]]*\]', 'The document does not record your pulse rate.', cleaned_response_text)
            cleaned_response_text = re.sub(r'\[[^\]]*[Bb]lood[^\]]*[Pp]ressure[^\]]*\]', 'The document does not record your blood pressure.', cleaned_response_text)
            cleaned_response_text = re.sub(r'\[[^\]]*[Tt]emperature[^\]]*\]', 'The document does not record your temperature.', cleaned_response_text)
            cleaned_response_text = re.sub(r'\[[^\]]*[Pp]atient[^\]]*[Nn]ame[^\]]*\]', '', cleaned_response_text)

            cleaned_response_text = re.sub(
                r'([^.?!]*\bpulse rate was measured at)\s+(?![0-9])bpm([^.?!]*\.)',
                r"\1, but the document doesn't list the exact number\2",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )
            cleaned_response_text = re.sub(
                r'([^.?!]*\btemperature was recorded as)\s+(?![0-9])°c([^.?!]*\.)',
                r"\1, but the exact value isn't clearly written\2",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )
            cleaned_response_text = re.sub(
                r'([^.?!]*\bblood pressure was measured at)\s+(?![0-9])mmhg([^.?!]*\.)',
                r"\1, but it doesn't show the exact reading\2",
                cleaned_response_text,
                flags=re.IGNORECASE,
            )

            if re.search(r'\d+\s*(bpm|mmhg|°c|°f|g/dl|mg/dl|mEq/L)', cleaned_response_text, re.IGNORECASE):
                cleaned_response_text = re.sub(
                    r'the document does not specify the exact value for these measurements\.',
                    '',
                    cleaned_response_text,
                    flags=re.IGNORECASE,
                )

            cleaned_response_text = re.sub(r'\(\d{4}-\d{2}-\d{2}\)', '', cleaned_response_text)

            lines = cleaned_response_text.split('\n')
            filtered_lines = []
            skip_section = False
            section_headers = [
                'dates and timestamps', 'dates', 'timestamps', 'summary', 'dates:', 'timestamps:',
                'summary:', 'next visit', 'next visit:', 'dates and timestamps:'
            ]

            for line in lines:
                stripped = line.strip()

                if skip_section and not stripped:
                    continue

                if stripped.startswith('---') and ('📄' in stripped or 'Documents' in stripped or 'Notes' in stripped):
                    skip_section = True
                    continue

                if any(header in stripped.lower() for header in section_headers):
                    skip_section = True
                    continue

                if re.match(r'^\(?\d{4}-\d{2}-\d{2}\)?$', stripped):
                    continue

                if re.match(r'^\[.*[Rr]edacted.*\]$', stripped):
                    continue

                if skip_section and stripped:
                    is_metadata = (
                        stripped.startswith('*') or stripped.startswith('-') or
                        stripped.startswith('•') or
                        (stripped.startswith('(') and re.search(r'\d{4}', stripped)) or
                        any(keyword in stripped.lower() for keyword in ['date:', 'timestamp:', 'next visit:', 'redacted'])
                    )
                    if not is_metadata:
                        skip_section = False

                if not skip_section:
                    filtered_lines.append(line)

            cleaned_response_text = '\n'.join(filtered_lines).strip()

            lines = cleaned_response_text.split('\n')
            if lines:
                last_line = lines[-1].strip()
                if last_line.endswith(',') and len(last_line) < 50:
                    lines = lines[:-1]
                cleaned_response_text = '\n'.join(lines).strip()

            disclaimer_patterns = [
                r'disclaimer.*intended for informational purposes only.*',
                r'always consult with your healthcare provider for personalized medical advice.*',
                r'if you have any questions about these results, please consult with a healthcare professional.*',
            ]
            for pat in disclaimer_patterns:
                cleaned_response_text = re.sub(pat, '', cleaned_response_text, flags=re.IGNORECASE | re.DOTALL)

            cleaned_response_text = re.sub(r'[ \t]+', ' ', cleaned_response_text)
            cleaned_response_text = re.sub(r'\s*\n\s*', '\n', cleaned_response_text).strip()

            from app.services.llm.model import LLMResponse
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
                context_used=latest_doc_text[:500] + "..." if len(latest_doc_text) > 500 else latest_doc_text,
                num_sources=1,
                sources_summary=[{"source_type": "document", "source_id": latest_doc.id, "relevance": 1.0}],  # type: ignore[union-attr]
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
            
            context_text = context_result.synthesized_context.full_context
            is_summary_query = any(keyword in question.lower() for keyword in ['summarize', 'summary', 'overview', 'findings', 'key information', 'what information', 'what does'])
            
            if not is_summary_query:
                can_answer, reason_if_no = self.evidence_validator.can_answer_from_context(question, context_text)
                
                if not can_answer:
                    self.logger.warning(
                        "Evidence gating blocked answer: question=%s reason=%s",
                        question,
                        reason_if_no
                    )
                    assistant_message = await self.conversation_manager.add_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=reason_if_no or "The document does not record this information.",
                    )
                    return RAGResponse(
                        answer=reason_if_no or "The document does not record this information.",
                        llm_response=LLMResponse(
                            text=reason_if_no or "The document does not record this information.",
                            tokens_generated=0,
                            tokens_input=0,
                            generation_time_ms=0,
                            finish_reason="evidence_gating",
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
            
            if question_mode == 'GENERAL_MEDICAL':
                question_terms = set(re.findall(r'\b\w+\b', question.lower()))
                context_terms = set(re.findall(r'\b\w+\b', context_text.lower()))
                overlap = question_terms.intersection(context_terms)
                
                if len(overlap) / max(len(question_terms), 1) < 0.3:
                    self.logger.info("General medical question with low context overlap, will note this in response")

        if not context_result.synthesized_context.total_chunks_used:
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

            retrieval_results_count = len(context_result.ranked_results) if hasattr(context_result, 'ranked_results') else 0
            max_similarity = 0.0
            if hasattr(context_result, 'ranked_results') and context_result.ranked_results:
                max_similarity = max((r.final_score for r in context_result.ranked_results), default=0.0)

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

        # Build sources summary
        if context_result is not None:
            sources_summary = [
                {
                    "source_type": r.result.source_type,
                    "source_id": r.result.source_id,
                    "relevance": r.final_score,
                }
                for r in context_result.ranked_results[:5]
            ]

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
                r'\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?',
                '',
                clean_prompt,
            )
            
            if question_mode == 'GENERAL_MEDICAL':
                clean_prompt = (
                    f"{clean_prompt}\n\n"
                    "IMPORTANT: The user is asking a general medical question. "
                    "If this information is NOT explicitly in the document context above, "
                    "you must say: 'The document does not explain [topic]. "
                    "I can provide a general explanation if you'd like, but it won't be from your medical records.' "
                    "Do NOT automatically provide general medical knowledge unless the user explicitly asks for it."
                )

            llm_response = await self.llm_service.generate(
                prompt=clean_prompt,
                max_new_tokens=max_new_tokens,
                conversation_history=conversation_history,
            )

        cleaned_response_text = llm_response.text
        
        is_valid, validation_error = self.evidence_validator.validate_response(
            cleaned_response_text,
            context_text,
            question
        )
        
        if not is_valid and validation_error:
            self.logger.warning(
                "Response validation failed: question=%s error=%s",
                question,
                validation_error
            )
            cleaned_response_text = validation_error

        cleaned_response_text = cleaned_response_text.replace("--- 📄 Documents ---", "")
        cleaned_response_text = cleaned_response_text.replace("--- Documents ---", "")
        cleaned_response_text = cleaned_response_text.replace("--- 📝 Additional Notes ---", "")

        cleaned_response_text = re.sub(r'\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?', '', cleaned_response_text)
        cleaned_response_text = cleaned_response_text.replace("[Redacted]", "")
        
        cleaned_response_text = re.sub(r'\[[^\]]*[Vv]alue[^\]]*\]', 'The document does not record this information.', cleaned_response_text)
        cleaned_response_text = re.sub(r'\[[^\]]*[Pp]ulse[^\]]*[Rr]ate[^\]]*\]', 'The document does not record your pulse rate.', cleaned_response_text)
        cleaned_response_text = re.sub(r'\[[^\]]*[Bb]lood[^\]]*[Pp]ressure[^\]]*\]', 'The document does not record your blood pressure.', cleaned_response_text)
        cleaned_response_text = re.sub(r'\[[^\]]*[Tt]emperature[^\]]*\]', 'The document does not record your temperature.', cleaned_response_text)
        cleaned_response_text = re.sub(r'\[[^\]]*[Pp]atient[^\]]*[Nn]ame[^\]]*\]', '', cleaned_response_text)

        cleaned_response_text = re.sub(r'(?i)\[insert[^]]+here\]', '', cleaned_response_text)
        cleaned_response_text = re.sub(r'(?i)\[mention[^\]]*e\.g\.[^\]]+\]', '', cleaned_response_text)
        cleaned_response_text = re.sub(r'\bof\s{2,}bpm\b', 'bpm', cleaned_response_text)
        cleaned_response_text = re.sub(
            r'[^.?!]*\bpulse rate was measured at\s*bpm[^.?!]*\.',
            "The document shows that your pulse rate was measured, but it doesn't list the exact number.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )
        cleaned_response_text = re.sub(
            r'[^.?!]*\btemperature was recorded as\s*°c[^.?!]*\.',
            "The document notes that your temperature was checked, but the exact value isn't clearly written.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )
        cleaned_response_text = re.sub(
            r'[^.?!]*\bblood pressure was measured at\s*mmhg[^.?!]*\.',
            "The document indicates that your blood pressure was measured, but it doesn't show the exact reading.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )
        
        cleaned_response_text = re.sub(
            r'\bpulse rate was recorded as\s+\*+\s+beats per minute',
            "The document does not record your pulse rate.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )
        cleaned_response_text = re.sub(
            r'\bpulse rate was\s+\*+\s+beats per minute',
            "The document does not record your pulse rate.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )
        
        # Remove hallucinated interpretations that aren't in the document
        hallucination_patterns = [
            (r'further\s+testing\s+confirmed', 'The document does not state this.'),
            (r'normal\s+findings\s+during\s+the\s+examination', 'The document does not describe the examination findings.'),
            (r'your\s+doctor\s+will\s+review\s+this\s+result', ''),
            (r'your\s+doctor\s+will\s+provide\s+more\s+detailed\s+explanations', ''),
            (r'to\s+determine\s+if\s+it\s+needs\s+further\s+investigation', ''),
            (r'this\s+is\s+within\s+the\s+typical\s+range', ''),
            (r'this\s+is\s+within\s+the\s+normal\s+range', ''),
            (r'performed\s+on\s+January\s+\d{1,2}(?:st|nd|rd|th)?,\s+2026', ''),  # Remove invented dates
            (r'performed\s+on\s+\w+\s+\d{1,2}(?:st|nd|rd|th)?,\s+2026', ''),  # Remove invented dates
        ]
        for pattern, replacement in hallucination_patterns:
            cleaned_response_text = re.sub(pattern, replacement, cleaned_response_text, flags=re.IGNORECASE)
        
        cleaned_response_text = re.sub(
            r'\btemperature was recorded as\s+\*+\s*°c',
            "The document does not record your temperature.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )
        cleaned_response_text = re.sub(
            r'\bblood pressure was recorded as\s+\*+\s*mmhg',
            "The document does not record your blood pressure.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )
        
        # Remove any remaining placeholder patterns
        cleaned_response_text = re.sub(
            r'\b\w+\s+was\s+(recorded|measured|checked)\s+as\s+\*{2,}',
            lambda m: f"The document does not record your {m.group(0).split()[0]}.",
            cleaned_response_text,
            flags=re.IGNORECASE,
        )

        cleaned_response_text = re.sub(r'\(\d{4}-\d{2}-\d{2}\)', '', cleaned_response_text)

        lines = cleaned_response_text.split('\n')
        filtered_lines = []
        skip_section = False
        section_headers = [
            'dates and timestamps', 'dates', 'timestamps', 'summary', 'dates:', 'timestamps:',
            'summary:', 'next visit', 'next visit:', 'dates and timestamps:'
        ]

        for line in lines:
            stripped = line.strip()

            # Skip empty lines if we're in skip mode
            if skip_section and not stripped:
                continue

            # Skip section marker lines
            if stripped.startswith('---') and ('📄' in stripped or 'Documents' in stripped or 'Notes' in stripped):
                skip_section = True
                continue

            # Skip section headers
            if any(header in stripped.lower() for header in section_headers):
                skip_section = True
                continue

            # Skip lines that are just date patterns or metadata
            if re.match(r'^\(?\d{4}-\d{2}-\d{2}\)?$', stripped):
                continue

            # Skip lines that are just "[Redacted]" or similar
            if re.match(r'^\[.*[Rr]edacted.*\]$', stripped):
                continue

            # End skip mode when we hit real content
            if skip_section and stripped:
                # Real content is not a list item starting with *, -, •, or (
                # and doesn't contain common metadata keywords
                is_metadata = (
                    stripped.startswith('*') or stripped.startswith('-') or
                    stripped.startswith('•') or
                    (stripped.startswith('(') and re.search(r'\d{4}', stripped)) or
                    any(keyword in stripped.lower() for keyword in ['date:', 'timestamp:', 'next visit:', 'redacted'])
                )
                if not is_metadata:
                    skip_section = False

            if not skip_section:
                filtered_lines.append(line)

            cleaned_response_text = '\n'.join(filtered_lines).strip()

        lines = cleaned_response_text.split('\n')
        if lines:
            last_line = lines[-1].strip()
            if last_line.endswith(',') and len(last_line) < 50:
                lines = lines[:-1]
            cleaned_response_text = '\n'.join(lines).strip()

        disclaimer_patterns = [
            r'disclaimer.*intended for informational purposes only.*',
            r'always consult with your healthcare provider for personalized medical advice.*',
            r'if you have any questions about these results, please consult with a healthcare professional.*',
        ]
        for pat in disclaimer_patterns:
            cleaned_response_text = re.sub(pat, '', cleaned_response_text, flags=re.IGNORECASE | re.DOTALL)

        # Clean up multiple spaces and normalize whitespace
        cleaned_response_text = re.sub(r'[ \t]+', ' ', cleaned_response_text)
        cleaned_response_text = re.sub(r'\s*\n\s*', '\n', cleaned_response_text).strip()

        # Create cleaned response
        from app.services.llm.model import LLMResponse
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
        conversation_id: Optional[UUID] = None,
        system_prompt: Optional[str] = None,
        max_context_tokens: int = 4000,
    ):
        """Stream answer generation.

        Yields:
            Text chunks as they are generated
        """
        # Fetch patient information for personalized greeting
        patient_result = await self.db.execute(
            select(Patient).where(Patient.id == patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        patient_first_name = patient.first_name if patient else None

        # Get or create conversation
        if conversation_id:
            conversation = await self.conversation_manager.get_conversation(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = await self.conversation_manager.create_conversation(patient_id)
            conversation_id = conversation.conversation_id

        # Add user message
        await self.conversation_manager.add_message(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )

        # Get context
        device = getattr(self.llm_service, "device", None)
        if not device:
            device = "cuda" if hasattr(self.llm_service, "stream_generate") else "cpu"
        effective_max_context_tokens = max_context_tokens
        if device in ("mps", "cpu"):
            effective_max_context_tokens = min(max_context_tokens, 2000)

        # For summary queries or document-related queries, use a lower similarity threshold
        min_score = 0.3
        enhanced_system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

        # Lower threshold for:
        # 1. Summary queries (need broader context)
        # 2. Questions about documents/images (vision extraction may have different terminology)
        is_summary_query = any(keyword in question.lower() for keyword in ['summarize', 'summary', 'overview', 'findings', 'key information', 'clear', 'easy-to-understand'])
        is_document_query = any(keyword in question.lower() for keyword in ['document', 'image', 'picture', 'photo', 'scan', 'report', 'what does', 'what is in', 'what information'])

        if is_summary_query or is_document_query:
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

        # Special case (streaming): summaries of the "most recent/latest document" should be grounded
        # in the actual latest processed document text (not just vector retrieval), to avoid generic output.
        wants_latest_doc_summary = (
            is_summary_query
            and any(
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
                if latest_doc and latest_doc.extracted_text and latest_doc.extracted_text.strip()
                else None
            )
            if latest_doc_text:
                # Build personalized greeting
                greeting = f"Hi {patient_first_name}," if patient_first_name else "Hi there,"
                
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
                    "- Do NOT add meta text like \"I understand\" or \"Here is the summary\".\n"
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
                    max_new_tokens=min(settings.llm_max_new_tokens, 256) if device in ("mps", "cpu") else settings.llm_max_new_tokens,
                    system_prompt=enhanced_system_prompt,
                    conversation_history=None,
                )
                text = (llm_response.text or "").strip()

                # Strip obvious artifacts/placeholders/disclaimers.
                text = text.replace("--- 📄 Documents ---", "").replace("--- Documents ---", "").replace("--- 📝 Additional Notes ---", "")
                text = re.sub(r'\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?', '', text)
                text = text.replace("[Redacted]", "")
                text = re.sub(r'(?i)\[insert[^]]+here\]', '', text)
                text = re.sub(r'(?i)\[mention[^\]]*e\.g\.[^\]]+\]', '', text)
                # Remove common "meta" preambles
                text = re.sub(r'(?is)^\s*(i understand[^.\n]*\.\s*)+', '', text)
                text = re.sub(r'(?im)^\s*here is the summary:\s*', '', text).lstrip()
                text = re.sub(
                    r'if you have any questions about these results, please consult with a healthcare professional\.?',
                    '',
                    text,
                    flags=re.IGNORECASE,
                )
                text = re.sub(
                    r'always consult with your healthcare provider for personalized medical advice.*',
                    '',
                    text,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                
                # Fix common OCR/spelling errors for customer-friendliness
                ocr_fixes = {
                    r'\bUrineysis\b': 'Urinalysis',
                    r'\bIsolazid\b': 'Isoniazid',  # Only if context suggests it's a medication
                    r'\bNR\b(?!\s*[A-Z])': 'not recorded',  # Replace standalone "NR" but not "NR Not tested"
                    r'\bNR\s+Not\s+tested\b': 'not recorded / not done',  # Gentler phrasing
                }
                for pattern, replacement in ocr_fixes.items():
                    text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
                
                # Remove banned phrases that indicate inference without evidence
                banned_phrases = self.evidence_validator.contains_banned_phrases(text)
                if banned_phrases:
                    self.logger.warning("Response contains banned phrases (possible hallucination): %s", banned_phrases)
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
                    r'\bHIV:\s*[A-Z]\s+Non-Reactive\b',
                    'HIV: Non-Reactive',
                    text,
                    flags=re.IGNORECASE
                )
                text = re.sub(
                    r'\bHIV:\s*[A-Z]\s+Reactive\b',
                    'HIV: Reactive',
                    text,
                    flags=re.IGNORECASE
                )
                
                # Fix "not tested" to gentler phrasing
                text = re.sub(
                    r'\bnot tested\b',
                    'not recorded / not done',
                    text,
                    flags=re.IGNORECASE
                )
                
                # Ensure second person is used (replace "a patient's" with "your")
                text = re.sub(
                    r'\ba patient\'?s\b',
                    'your',
                    text,
                    flags=re.IGNORECASE
                )
                text = re.sub(
                    r'\bthe patient\'?s\b',
                    'your',
                    text,
                    flags=re.IGNORECASE
                )
                
                # Fix "an [X] checkup" -> "your [X] checkup"
                text = re.sub(
                    r'\ban\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+checkup\b',
                    r'your \1 checkup',
                    text,
                    flags=re.IGNORECASE
                )
                text = re.sub(
                    r'\ban\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Profile\s+checkup\b',
                    r'your \1 checkup',
                    text,
                    flags=re.IGNORECASE
                )
                # Also fix "summarizes an" -> "summarizes your"
                text = re.sub(
                    r'summarizes\s+an\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+checkup\b',
                    r'summarizes your \1 checkup',
                    text,
                    flags=re.IGNORECASE
                )
                text = re.sub(
                    r'summarizes\s+an\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Profile\s+checkup\b',
                    r'summarizes your \1 checkup',
                    text,
                    flags=re.IGNORECASE
                )
                
                # Fix contradiction: If both "TB Screening: Positive" and "Screening outcome: Negative" appear separately, combine them
                if re.search(r'TB\s+Screening[:\s]+Positive', text, re.IGNORECASE) and \
                   re.search(r'Screening\s+outcome[:\s]+Negative', text, re.IGNORECASE):
                    # Replace the separate lines with combined version
                    # First, remove the TB Screening line
                    text = re.sub(
                        r'\*\s*TB\s+Screening[:\s]+Positive\s*\n',
                        '',
                        text,
                        flags=re.IGNORECASE
                    )
                    # Then replace the Screening outcome line with combined version
                    text = re.sub(
                        r'\*\s*Screening\s+outcome[:\s]+Negative\s*\n',
                        '* TB screening: Positive (the document also lists a screening outcome of "Negative"; please confirm with your clinic what this refers to)\n',
                        text,
                        flags=re.IGNORECASE
                    )
                    # Also handle if they're on the same line or in different formats
                    text = re.sub(
                        r'\*\s*TB\s+Screening[:\s]+Positive[^\n]*\n\s*\*\s*Screening\s+outcome[:\s]+Negative',
                        '* TB screening: Positive (the document also lists a screening outcome of "Negative"; please confirm with your clinic what this refers to)',
                        text,
                        flags=re.IGNORECASE | re.MULTILINE
                    )

                # Fix placeholder asterisks (****) in vital signs - LLM sometimes generates these when value is missing
                # Replace with explicit "not recorded" message
                text = re.sub(
                    r'\bpulse rate was recorded as\s+\*+\s+beats per minute',
                    "The document does not record your pulse rate.",
                    text,
                    flags=re.IGNORECASE,
                )
                text = re.sub(
                    r'\bpulse rate was\s+\*+\s+beats per minute',
                    "The document does not record your pulse rate.",
                    text,
                    flags=re.IGNORECASE,
                )
                text = re.sub(
                    r'\btemperature was recorded as\s+\*+\s*°c',
                    "The document does not record your temperature.",
                    text,
                    flags=re.IGNORECASE,
                )
                text = re.sub(
                    r'\bblood pressure was recorded as\s+\*+\s*mmhg',
                    "The document does not record your blood pressure.",
                    text,
                    flags=re.IGNORECASE,
                )
                
                # Remove any remaining placeholder patterns
                text = re.sub(
                    r'\b\w+\s+was\s+(recorded|measured|checked)\s+as\s+\*{2,}',
                    lambda m: f"The document does not record your {m.group(0).split()[0]}.",
                    text,
                    flags=re.IGNORECASE,
                )
                
                # Remove banned phrases that indicate inference without evidence
                banned_phrases = self.evidence_validator.contains_banned_phrases(text)
                if banned_phrases:
                    self.logger.warning("Response contains banned phrases (possible hallucination): %s", banned_phrases)
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
                    if re.search(rf'\b{re.escape(unit)}\b', text, flags=re.IGNORECASE) and not re.search(r'\d', text):
                        # If the entire response has no digits but mentions units, strip those sentences.
                        text = re.sub(rf'[^.?!]*\b{re.escape(unit)}\b[^.?!]*[.?!]', '', text, flags=re.IGNORECASE)

                text = re.sub(r'[ \t]+', ' ', text)
                text = re.sub(r'\s*\n\s*', '\n', text).strip()

                if text:
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

        if not context_result.synthesized_context.total_chunks_used:
            # Mirror the diagnostic behaviour from ask() but in streaming form.
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

        # Clean up the prompt to remove section markers
        clean_prompt = context_result.prompt
        clean_prompt = clean_prompt.replace("--- 📄 Documents ---", "")
        clean_prompt = clean_prompt.replace("--- Documents ---", "")
        clean_prompt = clean_prompt.replace("--- 📝 Additional Notes ---", "")
        # Remove [Redacted] from context - but preserve actual medical data
        clean_prompt = re.sub(r'\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?', '', clean_prompt)

        # Stream generation
        full_answer = ""
        # MPS/CPU streaming can hang; fall back to single-shot generation.
        if device in ("mps", "cpu"):
            max_new_tokens = min(settings.llm_max_new_tokens, 256)
            llm_response = await self.llm_service.generate(
                prompt=clean_prompt,
                max_new_tokens=max_new_tokens,
                conversation_history=None,
            )
            full_answer = llm_response.text or ""
            # Apply the same cleaning we do below before yielding
            if full_answer:
                cleaned_chunk = full_answer
                # Strip section markers
                cleaned_chunk = cleaned_chunk.replace("--- 📄 Documents ---", "")
                cleaned_chunk = cleaned_chunk.replace("--- Documents ---", "")
                cleaned_chunk = cleaned_chunk.replace("--- 📝 Additional Notes ---", "")
                # Strip [Redacted] and template placeholders
                cleaned_chunk = re.sub(r'\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?', '', cleaned_chunk)
                cleaned_chunk = cleaned_chunk.replace("[Redacted]", "")
                cleaned_chunk = re.sub(r'\[insert[^]]+here\]', '', cleaned_chunk, flags=re.IGNORECASE)
                # Basic cleanup of leftover patterns
                cleaned_chunk = re.sub(r'\bof\s+bpm\b', 'bpm', cleaned_chunk)
                full_answer = cleaned_chunk
                if cleaned_chunk.strip():
                    yield cleaned_chunk
        else:
            async for chunk in self.llm_service.stream_generate(
                prompt=clean_prompt,
                system_prompt=None,  # Already in prompt
            ):
                # Filter out section markers and placeholders as they stream
                cleaned_chunk = chunk
                if "--- 📄 Documents ---" in cleaned_chunk or "--- Documents ---" in cleaned_chunk:
                    cleaned_chunk = cleaned_chunk.replace("--- 📄 Documents ---", "")
                    cleaned_chunk = cleaned_chunk.replace("--- Documents ---", "")
                    cleaned_chunk = cleaned_chunk.replace("--- 📝 Additional Notes ---", "")
                # Remove [Redacted] and template-style placeholders in the streamed text
                cleaned_chunk = re.sub(r'\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?', '', cleaned_chunk)
                cleaned_chunk = cleaned_chunk.replace("[Redacted]", "")
                cleaned_chunk = re.sub(r'(?i)\[insert[^]]+here\]', '', cleaned_chunk)
                cleaned_chunk = re.sub(r'(?i)\[mention[^\]]*e\.g\.[^\]]+\]', '', cleaned_chunk)
                # Skip disclaimer chunks entirely
                if "disclaimer" in cleaned_chunk.lower():
                    continue
                if cleaned_chunk:
                    full_answer += cleaned_chunk
                    yield cleaned_chunk

        # Post-process to clean up any remaining artifacts
        full_answer = full_answer.replace("--- 📄 Documents ---", "")
        full_answer = full_answer.replace("--- Documents ---", "")
        full_answer = full_answer.replace("--- 📝 Additional Notes ---", "")

        # Remove [Redacted] placeholders more aggressively
        full_answer = re.sub(r'\[Redacted\](?:\s*Date)?(?::\s*\[Redacted\])?', '', full_answer)
        full_answer = full_answer.replace("[Redacted]", "")

        # Remove template-style placeholders that indicate the model failed to fill in a value
        # Examples: "[Insert Pulse Rate Value Here]", "[mention specific test name, e.g., Cholesterol Panel]"
        full_answer = re.sub(r'(?i)\[insert[^]]+here\]', '', full_answer)
        full_answer = re.sub(r'(?i)\[mention[^\]]*e\.g\.[^\]]+\]', '', full_answer)
        # Clean up common leftover patterns like "of  bpm" (double space)
        full_answer = re.sub(r'\bof\s{2,}bpm\b', 'bpm', full_answer)

        # Remove date patterns like "(2026-01-27)"
        full_answer = re.sub(r'\(\d{4}-\d{2}-\d{2}\)', '', full_answer)

        # Remove document structure artifacts - filter out lines that look like section headers
        lines = full_answer.split('\n')
        filtered_lines = []
        skip_section = False
        section_headers = [
            'dates and timestamps', 'dates', 'timestamps', 'summary', 'dates:', 'timestamps:',
            'summary:', 'next visit', 'next visit:', 'dates and timestamps:'
        ]

        for line in lines:
            stripped = line.strip()

            # Skip empty lines if we're in skip mode
            if skip_section and not stripped:
                continue

            # Skip section marker lines
            if stripped.startswith('---') and ('📄' in stripped or 'Documents' in stripped or 'Notes' in stripped):
                skip_section = True
                continue

            # Skip section headers
            if any(header in stripped.lower() for header in section_headers):
                skip_section = True
                continue

            # Skip lines that are just date patterns or metadata
            if re.match(r'^\(?\d{4}-\d{2}-\d{2}\)?$', stripped):
                continue

            # Skip lines that are just "[Redacted]" or similar
            if re.match(r'^\[.*[Rr]edacted.*\]$', stripped):
                continue

            # End skip mode when we hit real content
            if skip_section and stripped:
                is_metadata = (
                    stripped.startswith('*') or stripped.startswith('-') or
                    stripped.startswith('•') or
                    (stripped.startswith('(') and re.search(r'\d{4}', stripped)) or
                    any(keyword in stripped.lower() for keyword in ['date:', 'timestamp:', 'next visit:', 'redacted'])
                )
                if not is_metadata:
                    skip_section = False

            if not skip_section:
                filtered_lines.append(line)

        full_answer = '\n'.join(filtered_lines).strip()

        # Remove trailing incomplete sentences
        lines = full_answer.split('\n')
        if lines:
            last_line = lines[-1].strip()
            if last_line.endswith(',') and len(last_line) < 50:
                lines = lines[:-1]
            full_answer = '\n'.join(lines).strip()

        # Remove disclaimer-style boilerplate if the model still emits it
        disclaimer_patterns = [
            r'disclaimer.*intended for informational purposes only.*',
            r'always consult with your healthcare provider for personalized medical advice.*',
        ]
        for pat in disclaimer_patterns:
            full_answer = re.sub(pat, '', full_answer, flags=re.IGNORECASE | re.DOTALL)

        # Clean up multiple spaces and normalize whitespace
        full_answer = re.sub(r'[ \t]+', ' ', full_answer)
        full_answer = re.sub(r'\s*\n\s*', '\n', full_answer).strip()

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
        system_prompt: Optional[str] = None,
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
        conversation_id: Optional[UUID] = None,
        system_prompt: Optional[str] = None,
        max_context_tokens: int = 4000,
        use_conversation_history: bool = True,
    ) -> tuple[RAGResponse, Optional[StructuredSummaryResponse]]:
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
        import time
        import json
        total_start = time.time()
        
        # Get or create conversation
        if conversation_id:
            conversation = await self.conversation_manager.get_conversation(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = await self.conversation_manager.create_conversation(patient_id)
            conversation_id = conversation.conversation_id
        
        # Add user message
        await self.conversation_manager.add_message(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )
        
        # Get latest document if summary query
        routing = self.query_router.route(question)
        wants_latest_doc = routing.task == QueryTask.DOC_SUMMARY and routing.temporal_intent == "latest"
        
        latest_doc: Document | None = None
        latest_doc_text: str | None = None
        if wants_latest_doc:
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
            if latest_doc and latest_doc.extracted_text and latest_doc.extracted_text.strip():
                latest_doc_text = latest_doc.extracted_text.strip()
        
        # Build JSON prompt
        context_text = latest_doc_text if latest_doc_text else "No specific document context available."
        
        json_prompt = (
            "You must respond with VALID JSON only. The JSON must start with '{' and end with '}'. "
            "No markdown, no code fences, no commentary before or after the JSON.\n\n"
            "JSON Schema:\n"
            "{\n"
            '  "overview": "One-sentence friendly overview",\n'
            '  "key_results": [\n'
            '    {"name": "Lab name", "value": "10.1", "value_num": 10.1, "unit": "g/dL", "date": "2026-01-27", "is_normal": true, "source_snippet": "exact text from document"},\n'
            '    {"name": "HIV Test", "value": "Negative", "value_num": null, "unit": null, "date": "2026-01-27", "is_normal": true, "source_snippet": "HIV: R Non-Reactive"},\n'
            '    ...\n'
            '  ],\n'
            '  "medications": [\n'
            '    {"name": "Med name", "dosage": "500mg", "frequency": "twice daily", "source_snippet": "exact text from document"},\n'
            '    ...\n'
            '  ],\n'
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
                validation_errors = self._validate_structured_response(structured, context_text)
                if validation_errors:
                    if attempt < max_retries - 1:
                        self.logger.warning("Validation failed on attempt %d: %s", attempt + 1, validation_errors)
                        json_prompt = (
                            f"The previous response had validation errors: {validation_errors}. "
                            "Every value must have a source_snippet showing where it came from in the document. "
                            "Do not invent values. Return ONLY valid JSON.\n\n" + json_prompt
                        )
                        continue
                    else:
                        self.logger.error("Validation failed after all retries: %s", validation_errors)
                
                break
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
                    rag_response = await self.ask(question, patient_id, conversation_id, system_prompt, max_context_tokens, use_conversation_history)
                    return rag_response, None
        
        # Convert structured to friendly text
        friendly_text = self._structured_to_friendly(structured) if structured else llm_response.text
        
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
            context_used=context_text[:500] + "..." if len(context_text) > 500 else context_text,
            num_sources=1 if latest_doc else 0,
            sources_summary=[{"source_type": "document", "source_id": latest_doc.id, "relevance": 1.0}] if latest_doc else [],
            conversation_id=conversation_id,
            message_id=assistant_message.message_id,
            context_time_ms=0.0,
            generation_time_ms=llm_response.generation_time_ms,
            total_time_ms=total_time,
        )
        
        return rag_response, structured
    
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
                if value_lower not in snippet_lower and value_lower not in context_lower:
                    errors.append(f"key_results[{i}].{result.name} value '{result.value}' not found in source_snippet or context")
        
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