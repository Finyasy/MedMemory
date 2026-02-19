"""Query routing and task classification for medical queries.

Routes user queries to appropriate task handlers based on intent.
"""

import re
from dataclasses import dataclass
from enum import Enum


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
    temporal_intent: str | None  # "trend", "latest", "historical"


class QueryRouter:
    """Routes user queries to appropriate task handlers.

    Uses AND logic for multi-pattern tasks (e.g., trend requires both intent AND entity).
    """

    # Intent patterns (what the user wants to do)
    TREND_INTENT_PATTERNS = [
        r"(how|has|has.*changed|trend|over time|over the past|improved|worsened|changed)",
    ]

    # Entity patterns (what the user is asking about)
    TREND_ENTITY_PATTERNS = [
        r"(hba1c|a1c|blood sugar|glucose|cholesterol|blood pressure|bp|weight|pulse|temperature)",
    ]

    MEDICATION_PATTERNS = [
        r"(medication|meds|drug|prescription|taking|stopped|discontinued|active)",
        r"(current|now|currently|what.*taking)",
    ]

    # Lab interpretation requires either interpretation words OR explicit "is this normal"
    LAB_INTERPRETATION_PATTERNS = [
        r"(explain|what does.*mean|interpret|significance|what.*mean)",
    ]

    LAB_NORMAL_CHECK_PATTERNS = [
        r"(is.*normal|normal.*range|out of range|abnormal|high|low)",
    ]

    LAB_CONTEXT_PATTERNS = [
        r"(lab|test|result|value|range)",
    ]

    SUMMARY_PATTERNS = [
        r"(summarize|summary|overview|key.*findings|what.*document|latest.*document)",
        r"(clear|easy.*understand|simple.*language)",
    ]

    VISION_PATTERNS = [
        r"(extract|read.*image|what.*see.*image|numbers.*image|table.*image)",
    ]

    def route(
        self, question: str, conversation_history: list | None = None
    ) -> RoutingResult:
        """Route a query to the appropriate task type.

        Uses AND logic for trend analysis (requires both intent AND entity).
        Uses OR logic for lab interpretation (interpretation words OR normal check).

        Args:
            question: User's question
            conversation_history: Previous conversation turns for context

        Returns:
            RoutingResult with task type and metadata
        """
        q_lower = question.lower()

        # Check for trend analysis: REQUIRES BOTH intent AND entity (AND logic)
        has_trend_intent = any(
            re.search(pattern, q_lower) for pattern in self.TREND_INTENT_PATTERNS
        )
        has_trend_entity = any(
            re.search(pattern, q_lower) for pattern in self.TREND_ENTITY_PATTERNS
        )

        if has_trend_intent and has_trend_entity:
            entities = self._extract_entities(q_lower)
            return RoutingResult(
                task=QueryTask.TREND_ANALYSIS,
                confidence=0.85,  # Higher confidence when both match
                extracted_entities=entities,
                temporal_intent="trend",
            )

        # Check for medication reconciliation
        med_matches = sum(
            1 for pattern in self.MEDICATION_PATTERNS if re.search(pattern, q_lower)
        )
        if med_matches >= 1:
            return RoutingResult(
                task=QueryTask.MEDICATION_RECONCILIATION,
                confidence=0.75,
                extracted_entities=[],
                temporal_intent="current",
            )

        # Check for lab interpretation: REQUIRES (interpretation words OR normal check) AND lab context
        has_lab_context = any(
            re.search(pattern, q_lower) for pattern in self.LAB_CONTEXT_PATTERNS
        )
        has_interpretation = any(
            re.search(pattern, q_lower) for pattern in self.LAB_INTERPRETATION_PATTERNS
        )
        has_normal_check = any(
            re.search(pattern, q_lower) for pattern in self.LAB_NORMAL_CHECK_PATTERNS
        )

        if has_lab_context and (has_interpretation or has_normal_check):
            entities = self._extract_entities(q_lower)
            return RoutingResult(
                task=QueryTask.LAB_INTERPRETATION,
                confidence=0.75,
                extracted_entities=entities,
                temporal_intent=None,
            )

        # Check for vision extraction
        vision_matches = sum(
            1 for pattern in self.VISION_PATTERNS if re.search(pattern, q_lower)
        )
        if vision_matches >= 1:
            return RoutingResult(
                task=QueryTask.VISION_EXTRACTION,
                confidence=0.85,
                extracted_entities=[],
                temporal_intent=None,
            )

        # Check for document summary
        summary_matches = sum(
            1 for pattern in self.SUMMARY_PATTERNS if re.search(pattern, q_lower)
        )
        if summary_matches >= 1:
            return RoutingResult(
                task=QueryTask.DOC_SUMMARY,
                confidence=0.8,
                extracted_entities=[],
                temporal_intent="latest"
                if any(term in q_lower for term in ["latest", "most recent", "recent"])
                else None,
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
            "HbA1c": r"hba1c|a1c|hemoglobin.*a1c",
            "Blood Pressure": r"blood pressure|bp",
            "Cholesterol": r"cholesterol",
            "Glucose": r"glucose|blood sugar",
            "Weight": r"weight",
            "Pulse": r"pulse|heart rate",
            "Temperature": r"temperature|temp",
        }
        for name, pattern in patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                entities.append(name)
        return entities
