"""Optional MedASR KenLM-backed decoder helpers."""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any


class MedAsrLmDependencyError(RuntimeError):
    """Raised when optional MedASR LM decoder dependencies are unavailable."""


@dataclasses.dataclass(frozen=True)
class BeamScoreSummary:
    """Lightweight summary of one decoded beam."""

    text: str
    logit_score: float
    lm_score: float


def _restore_text(text: str) -> str:
    return text.replace(" ", "").replace("#", " ").replace("</s>", "").strip()


def estimate_beam_confidence(
    beam_summaries: Sequence[BeamScoreSummary],
    *,
    top_k: int = 5,
) -> float | None:
    """Estimate transcript confidence from top beam LM scores.

    The LM-backed decoder does not emit a calibrated confidence value, so this
    returns the posterior mass of the best beam among the top candidates using a
    softmax over cumulative LM scores. The result is intentionally conservative
    and is only used as a transcript-review gate.
    """

    if top_k < 2:
        raise ValueError("top_k must be at least 2.")

    ranked = [summary for summary in beam_summaries[:top_k] if summary.text]
    if len(ranked) < 2:
        return None

    max_score = max(summary.lm_score for summary in ranked)
    weights = [
        math.exp(max(summary.lm_score - max_score, -50.0))
        for summary in ranked
    ]
    total_weight = sum(weights)
    if total_weight <= 0.0:
        return None

    confidence = weights[0] / total_weight
    return max(0.0, min(1.0, confidence))


class LasrCtcBeamSearchDecoder:
    """Notebook-aligned beam-search decoder for MedASR CTC outputs."""

    def __init__(
        self,
        tokenizer: Any,
        *,
        kenlm_model_path: str,
        alpha: float,
        beta: float,
    ) -> None:
        try:
            import pyctcdecode
        except ModuleNotFoundError as exc:
            raise MedAsrLmDependencyError(
                "pyctcdecode is required for the MedASR LM-backed decoder."
            ) from exc

        vocab = [None for _ in range(tokenizer.vocab_size)]
        tokenizer_vocab = getattr(tokenizer, "vocab", None) or tokenizer.get_vocab()
        for token, index in tokenizer_vocab.items():
            if index < tokenizer.vocab_size:
                vocab[index] = token
        if any(piece is None for piece in vocab):
            raise MedAsrLmDependencyError(
                "MedASR tokenizer vocabulary is incomplete for LM-backed decoding."
            )

        vocab[0] = ""
        for index in range(1, len(vocab)):
            piece = vocab[index]
            if not piece.startswith("<") and not piece.endswith(">"):
                piece = "▁" + piece.replace("▁", "#")
            vocab[index] = piece

        self._decoder = pyctcdecode.build_ctcdecoder(
            vocab,
            kenlm_model_path,
            alpha=alpha,
            beta=beta,
        )
        self.last_beam_summaries: tuple[BeamScoreSummary, ...] = ()

    def decode_beams(self, *args: Any, **kwargs: Any):
        beams = self._decoder.decode_beams(*args, **kwargs)
        normalized_beams = []
        beam_summaries = []
        for beam in beams:
            restored_text = _restore_text(beam.text)
            normalized_beams.append(dataclasses.replace(beam, text=restored_text))
            beam_summaries.append(
                BeamScoreSummary(
                    text=restored_text,
                    logit_score=float(beam.logit_score),
                    lm_score=float(beam.lm_score),
                )
            )
        self.last_beam_summaries = tuple(beam_summaries)
        return normalized_beams


def build_medasr_lm_components(
    *,
    model_source: str,
    kenlm_model_path: Path,
    local_files_only: bool,
    cache_dir: str | None,
    token: str | None,
    alpha: float,
    beta: float,
) -> tuple[Any, LasrCtcBeamSearchDecoder]:
    try:
        import transformers
    except ModuleNotFoundError as exc:
        raise MedAsrLmDependencyError(
            "transformers is required for the MedASR LM-backed decoder."
        ) from exc

    feature_extractor_kwargs: dict[str, Any] = {
        "local_files_only": local_files_only,
    }
    tokenizer_kwargs: dict[str, Any] = {
        "local_files_only": local_files_only,
    }
    if cache_dir:
        feature_extractor_kwargs["cache_dir"] = cache_dir
        tokenizer_kwargs["cache_dir"] = cache_dir
    if token:
        feature_extractor_kwargs["token"] = token
        tokenizer_kwargs["token"] = token

    feature_extractor = transformers.LasrFeatureExtractor.from_pretrained(
        model_source,
        **feature_extractor_kwargs,
    )
    feature_extractor._processor_class = "LasrProcessorWithLM"
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        model_source,
        **tokenizer_kwargs,
    )
    decoder = LasrCtcBeamSearchDecoder(
        tokenizer,
        kenlm_model_path=str(kenlm_model_path),
        alpha=alpha,
        beta=beta,
    )
    return feature_extractor, decoder
