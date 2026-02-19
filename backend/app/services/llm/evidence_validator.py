"""Evidence validation to prevent hallucinations in medical RAG responses.

This module provides guardrails to ensure the LLM only uses information
that is explicitly present in the retrieved context.
"""

import logging
import re

logger = logging.getLogger("medmemory")


class EvidenceValidator:
    """Validates that questions can be answered from the provided context.

    Prevents hallucinations by checking if required evidence exists before
    allowing the LLM to generate a response.
    """

    REQUIRES_VALUE_PATTERNS = [
        r"\bpulse\s+rate\b",
        r"\bheart\s+rate\b",
        r"\bhr\b(?!\s+status)",
        r"\bblood\s+pressure\b",
        r"\bbp\b(?!\s+test)",
        r"\btemperature\b",
        r"\btemp\b(?!\s+test)",
        r"\bweight\b",
        r"\bheight\b",
        r"\bbmi\b",
    ]

    NUMERIC_LAB_PATTERNS = [
        r"\bhemoglobin\b",
        r"\bhba1c\b",
        r"\ba1c\b",
        r"\bglucose\b",
        r"\bcreatinine\b",
    ]

    SIMPLE_FACT_PATTERNS = [
        r"\bblood\s+group\b",
        r"\bhiv\b",
        r"\bhiv\s+status\b",
        r"\bhiv\s+test\b",
        r"\btb\s+screening\b",
        r"\bhepatitis\s+b\b",
        r"\bthyroid\b",
        r"\bultrasound\b",
        r"\bobstetric\b",
        r"\bgestation\b",
        r"\bhemoglobin\b",
        r"\bhb\b(?!\s+status)",
        r"\burinalysis\b",
        r"\burine\b",
        r"\bipt\b",
        r"\bisoniazid\b",
    ]

    BANNED_PHRASES = [
        r"general\s+physical\s+exam\s+showed",
        r"within\s+normal\s+limits",
        r"unremarkable",
        r"no\s+abnormalities\s+noted",
        r"routine\s+checks\s+showed",
        r"normal\s+findings",
        r"normal\s+examination",
    ]

    GENERAL_KNOWLEDGE_PATTERNS = [
        r"what\s+is\s+",
        r"tell\s+me\s+about\s+",
        r"explain\s+",
        r"how\s+does\s+",
        r"what\s+does\s+.*\s+mean",
        r"define\s+",
    ]

    RECORD_CONTEXT_PATTERNS = [
        r"\bmy\b",
        r"\bpatient\b",
        r"\brecords?\b",
        r"\bresults?\b",
        r"\blabs?\b",
        r"\bmedications?\b",
        r"\bpulse\b",
        r"\bblood\s+pressure\b",
        r"\btemperature\b",
        r"\bhemoglobin\b",
        r"\bhba1c\b",
    ]

    MEDICAL_NUMERIC_HINTS = [
        "pulse",
        "heart rate",
        "blood pressure",
        "temperature",
        "vital",
        "hemoglobin",
        "hba1c",
        "a1c",
        "glucose",
        "creatinine",
        "platelet",
        "wbc",
        "rbc",
        "hiv",
        "tb",
        "ultrasound",
        "medication",
        "dosage",
        "dose",
        "lab",
        "result",
        "weight",
        "height",
        "bmi",
    ]

    NUMERIC_UNIT_PATTERN = re.compile(
        r"\b(?:bpm|mmhg|mm\s*hg|°c|°f|g/dl|mg/dl|mmol/l|meq/l|ng/ml|kg|cm|mm)\b"
        r"|(?:\b\d{1,3}/\d{1,3}\b)"
        r"|(?:\b\d+(?:\.\d+)?\s*%)",
        re.IGNORECASE,
    )
    NUMERIC_TOKEN_PATTERN = re.compile(
        r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b|\b\d{1,3}/\d{1,3}\b|\b\d+(?:\.\d+)?\b"
    )
    NUMERIC_GROUNDING_SKIP_PATTERNS = [
        r"does\s+not\s+record",
        r"not\s+recorded",
        r"not\s+in\s+documents",
        r"i\s+do\s+not\s+know",
        r"not\s+clearly\s+written",
        r"not\s+specified",
    ]
    SOURCE_CITATION_PATTERN = re.compile(
        r"\bsource\s*:\s*[a-z_]+#(?:\d+|unknown)\b",
        re.IGNORECASE,
    )

    def can_answer_from_context(
        self, question: str, context_text: str
    ) -> tuple[bool, str | None]:
        """Check if question can be answered from context.

        Args:
            question: User's question
            context_text: Retrieved context from documents

        Returns:
            Tuple of (can_answer, reason_if_no)
        """
        question_lower = question.lower()
        context_lower = (context_text or "").lower()
        has_context = bool(context_text and len(context_text.strip()) >= 10)

        requires_value = False
        value_type = None

        for pattern in self.REQUIRES_VALUE_PATTERNS:
            if re.search(pattern, question_lower):
                requires_value = True
                value_type = pattern
                break

        if requires_value:
            if not has_context:
                return (
                    False,
                    f"The document does not record your {self._extract_term_name(value_type)}.",
                )
            search_pattern = rf"({value_type}).{{0,30}}\d+"
            if not re.search(search_pattern, context_lower, re.IGNORECASE):
                term_match = re.search(value_type, context_lower, re.IGNORECASE)
                if term_match:
                    start = max(0, term_match.start() - 30)
                    end = min(len(context_lower), term_match.end() + 30)
                    snippet = context_lower[start:end]
                    if not re.search(r"\d+", snippet):
                        return (
                            False,
                            f"The document does not record your {self._extract_term_name(value_type)}.",
                        )

                return (
                    False,
                    f"The document does not record your {self._extract_term_name(value_type)}.",
                )

        asks_for_numeric_value = any(
            token in question_lower
            for token in [
                "what is",
                "what's",
                "level",
                "value",
                "reading",
                "number",
            ]
        )
        if asks_for_numeric_value:
            for pattern in self.NUMERIC_LAB_PATTERNS:
                if not re.search(pattern, question_lower):
                    continue
                if not has_context:
                    return (
                        False,
                        f"The document does not record your {self._extract_term_name(pattern)}.",
                    )
                search_pattern = rf"({pattern}).{{0,40}}\d+(?:\.\d+)?"
                if not re.search(search_pattern, context_lower, re.IGNORECASE):
                    return (
                        False,
                        f"The document does not record your {self._extract_term_name(pattern)}.",
                    )
                break

        for pattern in self.SIMPLE_FACT_PATTERNS:
            if re.search(pattern, question_lower):
                if "blood group" in question_lower or "blood type" in question_lower:
                    if re.search(
                        r"blood\s+(group|type)[:\s]+[OAB]", context_lower, re.IGNORECASE
                    ) or re.search(r"\b[OAB](?:\s*[+-])?\b", context_lower):
                        return True, None
                elif "hiv" in question_lower:
                    if re.search(
                        r"hiv[:\s]+(non-?reactive|reactive|positive|negative)",
                        context_lower,
                        re.IGNORECASE,
                    ):
                        return True, None
                elif re.search(pattern, context_lower, re.IGNORECASE):
                    return True, None

        if not has_context:
            return False, "No relevant information found in the patient's records."

        return True, None

    def _extract_term_name(self, pattern: str) -> str:
        """Extract human-readable term name from regex pattern."""
        name = pattern.replace(r"\b", "").replace(r"\s+", " ").strip()
        mapping = {
            r"\bpulse\s+rate\b": "pulse rate",
            r"\bheart\s+rate\b": "heart rate",
            r"\bhr\b": "heart rate",
            r"\bblood\s+pressure\b": "blood pressure",
            r"\bbp\b": "blood pressure",
            r"\btemperature\b": "temperature",
            r"\btemp\b": "temperature",
            r"\bhemoglobin\b": "hemoglobin",
            r"\bhba1c\b": "HbA1c",
            r"\ba1c\b": "A1c",
            r"\bglucose\b": "glucose",
            r"\bcreatinine\b": "creatinine",
        }
        return mapping.get(pattern, name)

    def detect_question_mode(self, question: str) -> str:
        """Detect if question is record-based or general medical knowledge.

        Returns:
            'RECORD_BASED' or 'GENERAL_MEDICAL'
        """
        question_lower = question.lower()

        if any(
            re.search(pattern, question_lower)
            for pattern in self.RECORD_CONTEXT_PATTERNS
        ):
            return "RECORD_BASED"

        for pattern in self.GENERAL_KNOWLEDGE_PATTERNS:
            if re.search(pattern, question_lower):
                return "GENERAL_MEDICAL"

        return "RECORD_BASED"

    def contains_banned_phrases(self, text: str) -> list[str]:
        """Check if text contains banned phrases that indicate inference.

        Returns:
            List of banned phrases found
        """
        text_lower = text.lower()
        found = []

        for phrase_pattern in self.BANNED_PHRASES:
            if re.search(phrase_pattern, text_lower):
                found.append(phrase_pattern)

        return found

    def _split_sentences(self, text: str) -> list[str]:
        """Split free text into sentence-like units."""
        parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
        return [part.strip() for part in parts if part and part.strip()]

    def _looks_like_medical_numeric_claim(self, sentence_lower: str) -> bool:
        """Return True when sentence likely contains a medical numeric claim."""
        if self.NUMERIC_UNIT_PATTERN.search(sentence_lower):
            return True
        return any(hint in sentence_lower for hint in self.MEDICAL_NUMERIC_HINTS)

    def _number_token_in_context(self, token: str, context_lower: str) -> bool:
        """Check whether a numeric token is present in source context."""
        token = token.strip().lower()
        if not token:
            return True

        if re.match(r"^\d{1,3}/\d{1,3}$", token):
            return token in context_lower

        if re.match(r"^(19|20)\d{2}-\d{2}-\d{2}$", token):
            return token in context_lower

        if "." in token:
            trimmed = token.rstrip("0").rstrip(".")
            if token in context_lower or (trimmed and trimmed in context_lower):
                return True
            return False

        if len(token) <= 1:
            return True

        pattern = rf"\b{re.escape(token)}(?:\.0+)?\b"
        return re.search(pattern, context_lower) is not None

    def find_ungrounded_numeric_claims(
        self, response: str, context_text: str
    ) -> list[str]:
        """Find sentence-level numeric claims not supported by context."""
        if not response or not response.strip():
            return []
        if not context_text or not context_text.strip():
            return []

        context_lower = context_text.lower()
        unsupported_sentences: list[str] = []

        for sentence in self._split_sentences(response):
            sentence_lower = sentence.lower()

            if any(
                re.search(pattern, sentence_lower)
                for pattern in self.NUMERIC_GROUNDING_SKIP_PATTERNS
            ):
                continue

            numeric_tokens = self.NUMERIC_TOKEN_PATTERN.findall(sentence_lower)
            if not numeric_tokens:
                continue

            if not self._looks_like_medical_numeric_claim(sentence_lower):
                continue

            unsupported = [
                token
                for token in numeric_tokens
                if not self._number_token_in_context(token, context_lower)
            ]
            if not unsupported:
                continue

            has_units = self.NUMERIC_UNIT_PATTERN.search(sentence_lower) is not None
            if has_units or len(unsupported) == len(numeric_tokens):
                unsupported_sentences.append(sentence)

        return unsupported_sentences

    def enforce_numeric_grounding(
        self, response: str, context_text: str, refusal_message: str
    ) -> tuple[str, list[str]]:
        """Remove or refuse unsupported numeric claims from response text."""
        unsupported_sentences = self.find_ungrounded_numeric_claims(
            response=response,
            context_text=context_text,
        )
        if not unsupported_sentences:
            return response, []

        cleaned = response
        for sentence in unsupported_sentences:
            cleaned = cleaned.replace(sentence, " ").strip()

        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\s*\n\s*", "\n", cleaned)
        cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned).strip()

        if not cleaned:
            return refusal_message, unsupported_sentences

        return cleaned, unsupported_sentences

    def find_uncited_numeric_claims(self, response: str) -> list[str]:
        """Find numeric medical claims that do not include an inline source citation."""
        if not response or not response.strip():
            return []

        uncited_sentences: list[str] = []
        for sentence in self._split_sentences(response):
            sentence_lower = sentence.lower()

            if any(
                re.search(pattern, sentence_lower)
                for pattern in self.NUMERIC_GROUNDING_SKIP_PATTERNS
            ):
                continue

            numeric_tokens = self.NUMERIC_TOKEN_PATTERN.findall(sentence_lower)
            if not numeric_tokens:
                continue

            if not self._looks_like_medical_numeric_claim(sentence_lower):
                continue

            if self.SOURCE_CITATION_PATTERN.search(sentence) is None:
                uncited_sentences.append(sentence)

        return uncited_sentences

    def enforce_numeric_citations(
        self,
        response: str,
        refusal_message: str,
    ) -> tuple[str, list[str]]:
        """Remove numeric claim sentences without source citations; fail closed if empty."""
        uncited_sentences = self.find_uncited_numeric_claims(response)
        if not uncited_sentences:
            return response, []

        cleaned = response
        for sentence in uncited_sentences:
            cleaned = cleaned.replace(sentence, " ").strip()

        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\s*\n\s*", "\n", cleaned)
        cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned).strip()

        if not cleaned:
            return refusal_message, uncited_sentences

        return cleaned, uncited_sentences

    def validate_response(
        self, response: str, context_text: str, question: str
    ) -> tuple[bool, str | None]:
        """Validate that response is grounded in context.

        Args:
            response: LLM-generated response
            context_text: Source context
            question: Original question

        Returns:
            Tuple of (is_valid, error_message_if_invalid)
        """
        if not response or len(response.strip()) < 5:
            return True, None

        if re.search(r"\*{4,}", response):
            logger.warning("Response contains placeholder pattern: 4+ asterisks")
            question_lower = question.lower()
            if "pulse" in question_lower or "heart rate" in question_lower:
                return False, "The document does not record your pulse rate."
            elif "temperature" in question_lower or "temp" in question_lower:
                return False, "The document does not record your temperature."
            elif "blood pressure" in question_lower or "bp" in question_lower:
                return False, "The document does not record your blood pressure."
            else:
                return False, "The document does not record this information."

        if re.search(r"XX{2,}", response):
            logger.warning("Response contains placeholder pattern: multiple X's")
            question_lower = question.lower()
            if "pulse" in question_lower or "heart rate" in question_lower:
                return False, "The document does not record your pulse rate."
            elif "temperature" in question_lower or "temp" in question_lower:
                return False, "The document does not record your temperature."
            elif "blood pressure" in question_lower or "bp" in question_lower:
                return False, "The document does not record your blood pressure."
            else:
                return False, "The document does not record this information."

        if re.search(r"\[.*?(?:Redacted|Insert|mention).*?\]", response, re.IGNORECASE):
            logger.warning("Response contains template placeholder")

        banned = self.contains_banned_phrases(response)
        if banned:
            logger.warning(
                "Response contains banned phrases (possible hallucination): %s", banned
            )

        question_lower = question.lower()
        for pattern in self.REQUIRES_VALUE_PATTERNS:
            if re.search(pattern, question_lower):
                if not re.search(r"\d+", response):
                    if re.search(
                        r"(not\s+recorded|doesn\'?t\s+record|not\s+listed|not\s+shown|does not record)",
                        response,
                        re.IGNORECASE,
                    ):
                        return True, None
                    logger.warning(
                        "Question requires value but response doesn't provide number or 'not recorded'"
                    )

        return True, None
