"""Cross-encoder reranking for second-stage retrieval refinement."""

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import torch

from app.config import settings

if TYPE_CHECKING:
    from app.services.context.retriever import RetrievalResult

logger = logging.getLogger("medmemory")


@dataclass(frozen=True)
class CrossEncoderScore:
    """Rerank score output for a retrieval result."""

    result_id: int
    source_type: str
    score: float


class CrossEncoderReranker:
    """Lazy-loaded cross-encoder reranker with offline-safe fallback."""

    _instance: "CrossEncoderReranker | None" = None

    def __init__(self) -> None:
        self._model = None
        self._disabled_reason: str | None = None
        self.model_name = settings.llm_rerank_model
        self.device = self._detect_device()

    @classmethod
    def get_instance(cls) -> "CrossEncoderReranker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _detect_device(self) -> str:
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _load_model(self):
        if self._model is not None:
            return self._model
        if self._disabled_reason:
            return None

        try:
            from sentence_transformers import CrossEncoder
        except Exception as exc:
            self._disabled_reason = f"sentence-transformers unavailable: {exc}"
            logger.warning("Cross-encoder reranker disabled: %s", self._disabled_reason)
            return None

        try:
            self._model = CrossEncoder(
                self.model_name,
                device=self.device,
                max_length=512,
                trust_remote_code=True,
                local_files_only=(
                    settings.hf_hub_offline or settings.transformers_offline
                ),
            )
            logger.info(
                "Cross-encoder reranker loaded model=%s device=%s",
                self.model_name,
                self.device,
            )
            return self._model
        except Exception as exc:
            self._disabled_reason = str(exc)
            logger.warning(
                "Cross-encoder reranker unavailable (model=%s): %s",
                self.model_name,
                exc,
            )
            return None

    def rerank(
        self,
        *,
        query: str,
        results: list["RetrievalResult"],
    ) -> list[tuple["RetrievalResult", float]]:
        """Return reranked results with cross-encoder scores."""
        model = self._load_model()
        if model is None or not results:
            return []

        pairs = []
        for result in results:
            content = (result.content or "").strip()
            if len(content) > 4000:
                content = content[:4000]
            pairs.append([query, content])

        try:
            scores = model.predict(
                pairs,
                batch_size=8,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        except Exception as exc:
            logger.warning("Cross-encoder rerank failed: %s", exc)
            return []

        reranked = []
        for result, raw_score in zip(results, scores, strict=False):
            score = float(raw_score)
            normalized = 1 / (1 + math.exp(-score))
            reranked.append((result, normalized))

        reranked.sort(key=lambda item: item[1], reverse=True)
        return reranked
