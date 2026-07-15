#!/usr/bin/env python3
"""Evaluate MedMemory retrieval quality on a labeled retrieval_eval dataset.

This script runs the production retrieval path (QueryAnalyzer + HybridRetriever)
against a JSONL benchmark and emits:
1) predictions.jsonl
2) metrics_summary.json
3) report.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass(slots=True)
class RetrievalEvalExample:
    """Single retrieval evaluation row."""

    case_id: str
    query: str
    patient_id: int
    subdomain: str
    gold_chunk_ids: list[int]
    expected_source_types: list[str]
    expected_date_from: datetime | None
    expected_date_to: datetime | None
    metadata: dict[str, Any]


@dataclass(slots=True)
class RetrievalOutcome:
    """Result for one retrieval eval case."""

    case_id: str
    query: str
    patient_id: int
    subdomain: str
    gold_chunk_ids: list[int]
    retrieved_chunk_ids: list[int]
    first_relevant_rank: int | None
    source_match_top1: bool | None
    source_match_at_k: bool | None
    time_match_top1: bool | None
    time_match_at_k: bool | None
    retrieval_time_ms: float
    top_results: list[dict[str, Any]]
    query_intent: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=Path("data/rag_benchmark/retrieval_eval.jsonl"),
        help="JSONL retrieval benchmark file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/rag_retrieval_eval/current"),
        help="Directory where metrics and predictions are written.",
    )
    parser.add_argument(
        "--k-values",
        type=str,
        default="5,10,20",
        help="Comma-separated k values used for Recall@k metrics.",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.3,
        help="Minimum combined score passed to HybridRetriever.retrieve().",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional retrieval limit override (defaults to max(k-values)).",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=None,
        help="Optional cap on loaded evaluation rows.",
    )
    parser.add_argument(
        "--top-results-per-row",
        type=int,
        default=20,
        help="How many retrieved rows to store in predictions.jsonl output.",
    )
    return parser.parse_args()


def parse_k_values(raw: str) -> list[int]:
    values: list[int] = []
    for token in raw.split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        try:
            value = int(cleaned)
        except ValueError as exc:
            raise ValueError(f"Invalid k value '{cleaned}' in --k-values") from exc
        if value <= 0:
            raise ValueError("--k-values must contain positive integers.")
        values.append(value)
    if not values:
        raise ValueError("--k-values must include at least one integer.")
    return sorted(set(values))


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def load_eval_examples(path: Path, limit: int | None = None) -> list[RetrievalEvalExample]:
    """Load retrieval evaluation examples from JSONL."""
    if not path.exists():
        raise FileNotFoundError(f"Eval file not found: {path}")

    examples: list[RetrievalEvalExample] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        query = str(payload.get("query", "")).strip()
        if not query:
            raise ValueError(f"Missing query on line {idx}.")
        patient_id = int(payload["patient_id"])
        gold_chunk_ids_raw = payload.get("gold_chunk_ids", [])
        if not isinstance(gold_chunk_ids_raw, list):
            raise TypeError(f"gold_chunk_ids must be a list on line {idx}.")
        gold_chunk_ids = [int(chunk_id) for chunk_id in gold_chunk_ids_raw]
        if not gold_chunk_ids:
            raise ValueError(f"gold_chunk_ids cannot be empty on line {idx}.")

        source_types_raw = payload.get("expected_source_types", [])
        if source_types_raw is None:
            source_types_raw = []
        if not isinstance(source_types_raw, list):
            raise TypeError(f"expected_source_types must be a list on line {idx}.")
        expected_source_types = [str(source_type).lower() for source_type in source_types_raw]

        window_raw = payload.get("expected_time_window")
        expected_date_from: datetime | None = None
        expected_date_to: datetime | None = None
        if window_raw is not None:
            if not isinstance(window_raw, dict):
                raise TypeError(f"expected_time_window must be an object on line {idx}.")
            expected_date_from = _parse_datetime(window_raw.get("date_from"))
            expected_date_to = _parse_datetime(window_raw.get("date_to"))

        examples.append(
            RetrievalEvalExample(
                case_id=str(payload.get("id") or f"case-{idx}"),
                query=query,
                patient_id=patient_id,
                subdomain=str(payload.get("subdomain", "unknown")),
                gold_chunk_ids=gold_chunk_ids,
                expected_source_types=expected_source_types,
                expected_date_from=expected_date_from,
                expected_date_to=expected_date_to,
                metadata=payload.get("metadata", {}) if isinstance(payload.get("metadata", {}), dict) else {},
            )
        )

    if limit is not None:
        examples = examples[:limit]
    if not examples:
        raise ValueError(f"No eval examples found in {path}")
    return examples


def _is_in_window(
    value: datetime | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> bool:
    if value is None or date_from is None or date_to is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return date_from <= value <= date_to


def _build_outcome(
    *,
    example: RetrievalEvalExample,
    retrieval_results: list[Any],
    retrieval_time_ms: float,
    max_k: int,
    query_intent: str,
) -> RetrievalOutcome:
    gold_set = set(example.gold_chunk_ids)
    retrieved_chunk_ids = [int(result.id) for result in retrieval_results]
    first_relevant_rank: int | None = None
    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in gold_set:
            first_relevant_rank = rank
            break

    top_results: list[dict[str, Any]] = []
    for rank, result in enumerate(retrieval_results[:max_k], start=1):
        top_results.append(
            {
                "rank": rank,
                "chunk_id": int(result.id),
                "source_type": str(result.source_type),
                "source_id": int(result.source_id) if result.source_id is not None else None,
                "combined_score": float(result.combined_score),
                "semantic_score": float(result.semantic_score),
                "keyword_score": float(result.keyword_score),
                "rerank_score": float(result.rerank_score),
                "context_date": _iso_or_none(result.context_date),
                "is_gold": int(result.id) in gold_set,
            }
        )

    source_match_top1: bool | None = None
    source_match_at_k: bool | None = None
    expected_sources = set(example.expected_source_types)
    if expected_sources:
        top1_source = (
            str(retrieval_results[0].source_type).lower() if retrieval_results else None
        )
        source_match_top1 = top1_source in expected_sources if top1_source else False
        source_match_at_k = any(
            str(result.source_type).lower() in expected_sources
            for result in retrieval_results[:max_k]
        )

    time_match_top1: bool | None = None
    time_match_at_k: bool | None = None
    if example.expected_date_from and example.expected_date_to:
        top1_date = retrieval_results[0].context_date if retrieval_results else None
        time_match_top1 = _is_in_window(
            top1_date,
            example.expected_date_from,
            example.expected_date_to,
        )
        time_match_at_k = any(
            _is_in_window(
                result.context_date,
                example.expected_date_from,
                example.expected_date_to,
            )
            for result in retrieval_results[:max_k]
        )

    return RetrievalOutcome(
        case_id=example.case_id,
        query=example.query,
        patient_id=example.patient_id,
        subdomain=example.subdomain,
        gold_chunk_ids=example.gold_chunk_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        first_relevant_rank=first_relevant_rank,
        source_match_top1=source_match_top1,
        source_match_at_k=source_match_at_k,
        time_match_top1=time_match_top1,
        time_match_at_k=time_match_at_k,
        retrieval_time_ms=retrieval_time_ms,
        top_results=top_results,
        query_intent=query_intent,
    )


def _hit_at_k(outcome: RetrievalOutcome, k: int) -> bool:
    gold_set = set(outcome.gold_chunk_ids)
    return any(chunk_id in gold_set for chunk_id in outcome.retrieved_chunk_ids[:k])


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _match_rate(values: list[bool | None]) -> float | None:
    observed = [value for value in values if value is not None]
    if not observed:
        return None
    return sum(1.0 if value else 0.0 for value in observed) / len(observed)


def compute_aggregate_metrics(
    outcomes: list[RetrievalOutcome],
    *,
    k_values: list[int],
) -> dict[str, Any]:
    """Compute overall retrieval metrics from outcome rows."""
    if not outcomes:
        raise ValueError("Cannot compute metrics with zero outcomes.")

    n_examples = len(outcomes)
    max_k = max(k_values)
    metrics: dict[str, Any] = {
        "n_examples": n_examples,
    }

    for k in k_values:
        hits = sum(1 for outcome in outcomes if _hit_at_k(outcome, k))
        metrics[f"recall@{k}"] = hits / n_examples

    reciprocal_ranks = [
        (1.0 / outcome.first_relevant_rank)
        if outcome.first_relevant_rank is not None
        else 0.0
        for outcome in outcomes
    ]
    metrics["mrr"] = _mean(reciprocal_ranks)
    metrics["evidence_coverage_rate"] = metrics[f"recall@{max_k}"]
    metrics["no_result_rate"] = _mean(
        [1.0 if not outcome.retrieved_chunk_ids else 0.0 for outcome in outcomes]
    )
    metrics["avg_retrieval_time_ms"] = _mean(
        [float(outcome.retrieval_time_ms) for outcome in outcomes]
    )

    source_top1_match = _match_rate([outcome.source_match_top1 for outcome in outcomes])
    source_at_k_match = _match_rate([outcome.source_match_at_k for outcome in outcomes])
    if source_top1_match is not None:
        metrics["source_top1_match_rate"] = source_top1_match
        metrics["wrong_source_type_rate"] = 1.0 - source_top1_match
    if source_at_k_match is not None:
        metrics[f"source_match_rate@{max_k}"] = source_at_k_match
        metrics[f"source_type_miss_rate@{max_k}"] = 1.0 - source_at_k_match

    time_top1_match = _match_rate([outcome.time_match_top1 for outcome in outcomes])
    time_at_k_match = _match_rate([outcome.time_match_at_k for outcome in outcomes])
    if time_top1_match is not None:
        metrics["time_window_top1_match_rate"] = time_top1_match
        metrics["wrong_time_window_rate"] = 1.0 - time_top1_match
    if time_at_k_match is not None:
        metrics[f"time_window_match_rate@{max_k}"] = time_at_k_match
        metrics[f"time_window_miss_rate@{max_k}"] = 1.0 - time_at_k_match

    return metrics


def compute_subdomain_metrics(
    outcomes: list[RetrievalOutcome],
    *,
    k_values: list[int],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[RetrievalOutcome]] = {}
    for outcome in outcomes:
        grouped.setdefault(outcome.subdomain, []).append(outcome)

    summary: dict[str, dict[str, Any]] = {}
    for subdomain in sorted(grouped):
        summary[subdomain] = compute_aggregate_metrics(
            grouped[subdomain],
            k_values=k_values,
        )
    return summary


async def evaluate_examples(
    examples: list[RetrievalEvalExample],
    *,
    k_values: list[int],
    min_score: float,
    limit: int | None,
) -> list[RetrievalOutcome]:
    """Run retrieval evaluation by calling the production retriever path."""
    from app.database import get_db_context
    from app.services.context.analyzer import QueryAnalyzer
    from app.services.context.retriever import HybridRetriever
    from app.services.embeddings import EmbeddingService

    max_k = max(k_values)
    retrieval_limit = limit if limit is not None else max_k
    retrieval_limit = max(retrieval_limit, max_k)

    outcomes: list[RetrievalOutcome] = []

    async with get_db_context() as db:
        analyzer = QueryAnalyzer()
        embedding_service = EmbeddingService.get_instance()
        retriever = HybridRetriever(db=db, embedding_service=embedding_service)

        for example in examples:
            query_analysis = analyzer.analyze(example.query)
            retrieval_response = await retriever.retrieve(
                query_analysis=query_analysis,
                patient_id=example.patient_id,
                limit=retrieval_limit,
                min_score=min_score,
            )
            outcome = _build_outcome(
                example=example,
                retrieval_results=retrieval_response.results,
                retrieval_time_ms=float(retrieval_response.retrieval_time_ms),
                max_k=max_k,
                query_intent=query_analysis.intent.value,
            )
            outcomes.append(outcome)

    return outcomes


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True))
            handle.write("\n")


def _metric_cell(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _write_markdown_report(
    *,
    path: Path,
    summary: dict[str, Any],
    k_values: list[int],
) -> None:
    metrics = summary["metrics"]["overall"]
    subdomains = summary["metrics"]["subdomains"]
    max_k = max(k_values)

    lines = [
        "# Retrieval Evaluation",
        "",
        f"- `created_at`: {summary['created_at']}",
        f"- `eval_file`: {summary['eval_file']}",
        f"- `n_examples`: {summary['n_examples']}",
        "",
        "## Overall Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| MRR | {_metric_cell(metrics['mrr'])} |",
    ]

    for k in k_values:
        lines.append(f"| Recall@{k} | {_metric_cell(metrics[f'recall@{k}'])} |")

    lines.extend(
        [
            f"| Evidence Coverage (Recall@{max_k}) | {_metric_cell(metrics['evidence_coverage_rate'])} |",
            f"| No Result Rate | {_metric_cell(metrics['no_result_rate'])} |",
            f"| Avg Retrieval Time (ms) | {_metric_cell(metrics['avg_retrieval_time_ms'])} |",
            f"| Wrong Source Type Rate | {_metric_cell(metrics.get('wrong_source_type_rate'))} |",
            f"| Wrong Time Window Rate | {_metric_cell(metrics.get('wrong_time_window_rate'))} |",
            "",
            "## Subdomain Metrics",
            "",
            "| Subdomain | N | MRR | Recall@1 | Recall@5 | Recall@10 | Wrong Source | Wrong Time |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for subdomain, payload in subdomains.items():
        lines.append(
            "| "
            + " | ".join(
                [
                    subdomain,
                    _metric_cell(payload["n_examples"]),
                    _metric_cell(payload["mrr"]),
                    _metric_cell(payload.get("recall@1")),
                    _metric_cell(payload.get("recall@5")),
                    _metric_cell(payload.get("recall@10")),
                    _metric_cell(payload.get("wrong_source_type_rate")),
                    _metric_cell(payload.get("wrong_time_window_rate")),
                ]
            )
            + " |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(
    *,
    output_dir: Path,
    eval_file: Path,
    outcomes: list[RetrievalOutcome],
    k_values: list[int],
    config: dict[str, Any],
    top_results_per_row: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_rows: list[dict[str, Any]] = []
    for outcome in outcomes:
        predictions_rows.append(
            {
                "id": outcome.case_id,
                "query": outcome.query,
                "patient_id": outcome.patient_id,
                "subdomain": outcome.subdomain,
                "query_intent": outcome.query_intent,
                "gold_chunk_ids": outcome.gold_chunk_ids,
                "retrieved_chunk_ids": outcome.retrieved_chunk_ids,
                "first_relevant_rank": outcome.first_relevant_rank,
                "source_match_top1": outcome.source_match_top1,
                "source_match_at_k": outcome.source_match_at_k,
                "time_match_top1": outcome.time_match_top1,
                "time_match_at_k": outcome.time_match_at_k,
                "retrieval_time_ms": outcome.retrieval_time_ms,
                "top_results": outcome.top_results[:top_results_per_row],
            }
        )
    _write_jsonl(output_dir / "predictions.jsonl", predictions_rows)

    overall_metrics = compute_aggregate_metrics(outcomes, k_values=k_values)
    subdomain_metrics = compute_subdomain_metrics(outcomes, k_values=k_values)
    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "eval_file": str(eval_file),
        "n_examples": len(outcomes),
        "k_values": k_values,
        "config": config,
        "metrics": {
            "overall": overall_metrics,
            "subdomains": subdomain_metrics,
        },
    }
    (output_dir / "metrics_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    _write_markdown_report(
        path=output_dir / "report.md",
        summary=summary,
        k_values=k_values,
    )
    return summary


async def main_async() -> int:
    args = parse_args()
    k_values = parse_k_values(args.k_values)
    examples = load_eval_examples(args.eval_file, limit=args.max_examples)

    outcomes = await evaluate_examples(
        examples,
        k_values=k_values,
        min_score=args.min_score,
        limit=args.limit,
    )
    summary = write_outputs(
        output_dir=args.output_dir,
        eval_file=args.eval_file,
        outcomes=outcomes,
        k_values=k_values,
        config={
            "min_score": args.min_score,
            "limit": args.limit,
            "max_examples": args.max_examples,
        },
        top_results_per_row=args.top_results_per_row,
    )

    print("Retrieval evaluation complete.")
    print(json.dumps(summary["metrics"]["overall"], indent=2, ensure_ascii=True))
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
