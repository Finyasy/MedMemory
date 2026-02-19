"""Intent-aware decoding profiles for grounded medical generation."""

from dataclasses import dataclass

from app.config import settings
from app.services.context.analyzer import QueryIntent
from app.services.llm.query_router import QueryTask


@dataclass(frozen=True)
class DecodingProfile:
    """Generation decoding profile selected for a query."""

    label: str
    do_sample: bool
    temperature: float
    top_p: float


class IntentClassifier:
    """Classify query intent into factual vs reasoning decoding modes."""

    FACTUAL_INTENTS = {
        QueryIntent.LIST,
        QueryIntent.VALUE,
        QueryIntent.STATUS,
    }

    FACTUAL_TASKS = {
        QueryTask.MEDICATION_RECONCILIATION,
    }

    REASONING_TASKS = {
        QueryTask.DOC_SUMMARY,
        QueryTask.TREND_ANALYSIS,
        QueryTask.LAB_INTERPRETATION,
    }

    REASONING_KEYWORDS = (
        "summarize",
        "summary",
        "overview",
        "risk",
        "risks",
        "analy",
        "explain",
        "trend",
        "compare",
        "potential",
    )

    def classify(
        self,
        *,
        question: str,
        routing_task: QueryTask | None,
        query_intent: QueryIntent | None,
    ) -> str:
        """Return either factual or reasoning class for generation control."""
        lower = question.lower()

        if routing_task in self.REASONING_TASKS:
            return "reasoning"

        if any(token in lower for token in self.REASONING_KEYWORDS):
            return "reasoning"

        if query_intent in self.FACTUAL_INTENTS:
            return "factual"

        if routing_task in self.FACTUAL_TASKS:
            return "factual"

        return "factual"

    def decoding_profile(
        self,
        *,
        question: str,
        routing_task: QueryTask | None,
        query_intent: QueryIntent | None,
    ) -> DecodingProfile:
        """Map classified intent to generation decoding parameters."""
        label = self.classify(
            question=question,
            routing_task=routing_task,
            query_intent=query_intent,
        )
        if label == "reasoning":
            return DecodingProfile(
                label=label,
                do_sample=True,
                temperature=settings.llm_reasoning_temperature,
                top_p=settings.llm_reasoning_top_p,
            )

        return DecodingProfile(
            label=label,
            do_sample=False,
            temperature=0.0,
            top_p=1.0,
        )
