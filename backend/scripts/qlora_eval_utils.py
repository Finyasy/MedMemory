"""Utilities for baseline vs QLoRA generation evaluation."""

from __future__ import annotations

import re
from dataclasses import dataclass

_WS_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[a-z0-9]+", flags=re.IGNORECASE)
_FACT_PATTERNS = [
    # Numeric measurements with common clinical units.
    re.compile(
        r"\b\d+(?:\.\d+)?\s?(?:mg/dl|g/dl|mmol/l|mmhg|bpm|kg|lbs|cm|mm|iu/l|u/l|%|ml)\b",
        flags=re.IGNORECASE,
    ),
    # Calendar-like dates.
    re.compile(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b",
        flags=re.IGNORECASE,
    ),
    # Polarity findings.
    re.compile(
        r"\b(?:positive|negative|non-reactive|reactive|detected|not detected)\b",
        flags=re.IGNORECASE,
    ),
]


def normalize_text(value: str) -> str:
    """Normalize text for robust string matching."""
    normalized = value.strip().lower()
    normalized = _WS_RE.sub(" ", normalized)
    return normalized


def token_f1(prediction: str, reference: str) -> float:
    """Compute token-level F1 between two strings."""
    pred_tokens = _WORD_RE.findall(normalize_text(prediction))
    ref_tokens = _WORD_RE.findall(normalize_text(reference))
    if not pred_tokens and not ref_tokens:
        return 1.0
    if not pred_tokens or not ref_tokens:
        return 0.0

    pred_counts: dict[str, int] = {}
    ref_counts: dict[str, int] = {}
    for token in pred_tokens:
        pred_counts[token] = pred_counts.get(token, 0) + 1
    for token in ref_tokens:
        ref_counts[token] = ref_counts.get(token, 0) + 1

    overlap = 0
    for token, count in pred_counts.items():
        overlap += min(count, ref_counts.get(token, 0))

    precision = overlap / max(len(pred_tokens), 1)
    recall = overlap / max(len(ref_tokens), 1)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def extract_facts(text: str) -> set[str]:
    """Extract coarse-grained factual spans from free text."""
    facts: set[str] = set()
    norm = normalize_text(text)
    for pattern in _FACT_PATTERNS:
        for match in pattern.findall(norm):
            facts.add(normalize_text(match))
    return facts


@dataclass(slots=True)
class AggregateMetrics:
    exact_match: float
    contains_reference: float
    token_f1: float
    fact_precision: float
    fact_recall: float
    hallucination_rate: float
    n_examples: int


def compute_generation_metrics(
    predictions: list[str],
    references: list[str],
) -> AggregateMetrics:
    """Compute text-accuracy and factuality proxies for generation outputs."""
    if len(predictions) != len(references):
        raise ValueError("Predictions and references must have the same length.")
    if not predictions:
        raise ValueError("Predictions and references cannot be empty.")

    exact_hits = 0
    contains_hits = 0
    f1_total = 0.0
    fact_precision_total = 0.0
    fact_recall_total = 0.0
    hallucinated_examples = 0

    for pred, ref in zip(predictions, references, strict=True):
        pred_norm = normalize_text(pred)
        ref_norm = normalize_text(ref)
        if pred_norm == ref_norm:
            exact_hits += 1
        if ref_norm and ref_norm in pred_norm:
            contains_hits += 1

        f1_total += token_f1(pred, ref)

        pred_facts = extract_facts(pred)
        ref_facts = extract_facts(ref)
        overlap = pred_facts & ref_facts

        precision = len(overlap) / len(pred_facts) if pred_facts else 1.0
        recall = len(overlap) / len(ref_facts) if ref_facts else 1.0
        fact_precision_total += precision
        fact_recall_total += recall

        if pred_facts - ref_facts:
            hallucinated_examples += 1

    n = len(predictions)
    return AggregateMetrics(
        exact_match=exact_hits / n,
        contains_reference=contains_hits / n,
        token_f1=f1_total / n,
        fact_precision=fact_precision_total / n,
        fact_recall=fact_recall_total / n,
        hallucination_rate=hallucinated_examples / n,
        n_examples=n,
    )
