"""OCR refinement using the LLM to clean text and extract entities."""

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.services.llm import LLMService


@dataclass
class OcrRefinementResult:
    """Result of OCR refinement."""

    cleaned_text: str
    entities: dict[str, Any]
    raw_response: str


class OcrRefinementService:
    """Clean OCR text and extract medical entities with the LLM."""

    DEFAULT_SYSTEM_PROMPT = (
        "You clean OCR text from medical documents. "
        "Return only JSON with keys: cleaned_text, entities. "
        "entities is an object with arrays for medications, diagnoses, labs, procedures, and dates."
    )

    DEFAULT_USER_PROMPT = (
        "Clean the OCR text below and extract medical entities. "
        "Fix spacing, line breaks, and obvious OCR errors. "
        "Return JSON only.\n\nOCR TEXT:\n{raw_text}"
    )

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service or LLMService.get_instance()
        self.logger = logging.getLogger("medmemory")

    async def refine(self, raw_text: str) -> OcrRefinementResult:
        """Refine raw OCR text into cleaned text and entities."""
        text = raw_text.strip()
        if not text:
            return OcrRefinementResult(cleaned_text="", entities={}, raw_response="")

        prompt = self.DEFAULT_USER_PROMPT.format(raw_text=text)
        response = await self.llm_service.generate(
            prompt=prompt,
            system_prompt=self.DEFAULT_SYSTEM_PROMPT,
            max_new_tokens=settings.ocr_refinement_max_new_tokens,
        )
        response_text = response.text.strip()

        parsed = self._parse_json(response_text)
        if parsed is None:
            cleaned_text = response_text or text
            return OcrRefinementResult(
                cleaned_text=cleaned_text,
                entities={},
                raw_response=response_text,
            )

        cleaned_text = parsed.get("cleaned_text") or text
        entities = (
            parsed.get("entities") if isinstance(parsed.get("entities"), dict) else {}
        )

        return OcrRefinementResult(
            cleaned_text=cleaned_text,
            entities=entities,
            raw_response=response_text,
        )

    def _parse_json(self, payload: str) -> dict[str, Any] | None:
        """Parse JSON output from the model, with a fallback scan."""
        if not payload:
            return None

        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            pass

        start = payload.find("{")
        end = payload.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        candidate = payload[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            self.logger.warning("OCR refinement JSON parse failed")
            return None
