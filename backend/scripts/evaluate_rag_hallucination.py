#!/usr/bin/env python3
"""Evaluate MedMemory RAG hallucination guardrails on a fixed regression set.

This evaluation intentionally targets guardrail behavior (grounding/citation/
trend refusal logic) rather than raw model quality so it can run in CI without
downloading large checkpoints.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.services.llm.evidence_validator import EvidenceValidator
from app.services.llm.rag import RAGService
from scripts.qlora_eval_utils import compute_generation_metrics, normalize_text

DEFAULT_REFUSAL = "I do not know from the available records."
DEFAULT_CITATION_REFUSAL = "Not in documents."
SUPPORTED_TASKS = {
    "numeric_grounding",
    "numeric_citation",
    "question_mode",
    "context_gate",
    "trend_direct",
}


@dataclass(slots=True)
class EvalExample:
    """Single evaluation row loaded from JSONL."""

    case_id: str
    task: str
    payload: dict[str, Any]
    expected: str


@dataclass(slots=True)
class EvalRunResult:
    """Result bundle for reporting and gating."""

    predictions: list[str]
    references: list[str]
    rows: list[dict[str, Any]]
    policy_pass_rate: float


def compute_task_metrics(result: EvalRunResult) -> dict[str, dict[str, float | int]]:
    """Compute per-task quality metrics from eval rows."""
    grouped: dict[str, dict[str, Any]] = {}
    for row in result.rows:
        task = str(row["task"])
        bucket = grouped.setdefault(
            task,
            {
                "predictions": [],
                "references": [],
                "passed": 0,
            },
        )
        bucket["predictions"].append(str(row["prediction"]))
        bucket["references"].append(str(row["reference"]))
        if bool(row["passed"]):
            bucket["passed"] += 1

    task_metrics: dict[str, dict[str, float | int]] = {}
    for task in sorted(grouped):
        bucket = grouped[task]
        predictions = bucket["predictions"]
        references = bucket["references"]
        aggregate = compute_generation_metrics(predictions, references)
        n_examples = len(predictions)
        task_metrics[task] = {
            "n_examples": n_examples,
            "policy_pass_rate": bucket["passed"] / max(n_examples, 1),
            "exact_match": aggregate.exact_match,
            "token_f1": aggregate.token_f1,
            "fact_precision": aggregate.fact_precision,
            "fact_recall": aggregate.fact_recall,
            "hallucination_rate": aggregate.hallucination_rate,
        }
    return task_metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=Path("data/hallucination_rag_eval/eval.jsonl"),
        help="JSONL file with RAG hallucination regression examples.",
    )
    parser.add_argument(
        "--scope",
        type=str,
        default="baseline",
        choices=["baseline", "finetuned"],
        help="Scope name used in output metrics_summary.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/hallucination_eval/current"),
        help="Directory where metrics/report artifacts will be written.",
    )
    parser.add_argument(
        "--min-policy-pass-rate",
        type=float,
        default=1.0,
        help="Minimum exact policy pass-rate required for exit code 0.",
    )
    return parser.parse_args()


def load_eval_examples(path: Path) -> list[EvalExample]:
    """Load evaluation examples from JSONL."""
    if not path.exists():
        raise FileNotFoundError(f"Eval file not found: {path}")

    examples: list[EvalExample] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        task = str(payload["task"]).strip()
        if task not in SUPPORTED_TASKS:
            supported = sorted(SUPPORTED_TASKS)
            raise ValueError(
                f"Unsupported task '{task}' on line {idx}. Supported: {supported}"
            )
        expected = str(payload["expected"]).strip()
        if not expected:
            raise ValueError(f"Missing expected output on line {idx}.")
        case_id = str(payload.get("id") or f"case-{idx}")
        input_payload = payload.get("input", {})
        if not isinstance(input_payload, dict):
            raise TypeError(f"Example input must be an object on line {idx}.")
        examples.append(
            EvalExample(
                case_id=case_id,
                task=task,
                payload=input_payload,
                expected=expected,
            )
        )

    if not examples:
        raise ValueError(f"No eval examples found in {path}")
    return examples


def _build_eval_rag_service() -> RAGService:
    """Construct a minimal RAGService instance for deterministic helper calls."""

    class _StubLLM:
        pass

    class _StubContext:
        pass

    class _StubConversation:
        pass

    return RAGService(
        db=None,  # type: ignore[arg-type]
        llm_service=_StubLLM(),  # type: ignore[arg-type]
        context_engine=_StubContext(),  # type: ignore[arg-type]
        conversation_manager=_StubConversation(),  # type: ignore[arg-type]
    )


def _to_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _run_example(
    *,
    example: EvalExample,
    validator: EvidenceValidator,
    rag: RAGService,
) -> str:
    task = example.task
    payload = example.payload

    if task == "numeric_grounding":
        response = str(payload["response"])
        context_text = str(payload.get("context_text", ""))
        refusal_message = str(payload.get("refusal_message", DEFAULT_REFUSAL))
        cleaned, _unsupported = validator.enforce_numeric_grounding(
            response=response,
            context_text=context_text,
            refusal_message=refusal_message,
        )
        return cleaned

    if task == "numeric_citation":
        response = str(payload["response"])
        refusal_message = str(payload.get("refusal_message", DEFAULT_CITATION_REFUSAL))
        cleaned, _uncited = validator.enforce_numeric_citations(
            response=response,
            refusal_message=refusal_message,
        )
        return cleaned

    if task == "question_mode":
        question = str(payload["question"])
        return validator.detect_question_mode(question)

    if task == "context_gate":
        question = str(payload["question"])
        context_text = str(payload.get("context_text", ""))
        can_answer, reason = validator.can_answer_from_context(
            question=question, context_text=context_text
        )
        return "ALLOW" if can_answer else (reason or "BLOCK")

    if task == "trend_direct":
        points = payload.get("points", [])
        if not isinstance(points, list):
            raise TypeError(f"trend_direct points must be a list for {example.case_id}")
        structured_results = []
        for point in points:
            if not isinstance(point, dict):
                raise TypeError(
                    f"trend_direct point must be an object for {example.case_id}"
                )
            name = str(point["name"])
            value = str(point["value"])
            unit = str(point.get("unit", "")).strip()
            date = _to_datetime(str(point["date"]))

            content = f"Lab: {name} = {value}"
            if unit:
                content += f" {unit}"

            structured_results.append(
                SimpleNamespace(
                    result=SimpleNamespace(
                        source_type="lab_result",
                        source_id=point.get("source_id"),
                        content=content,
                        context_date=date,
                    ),
                    final_score=float(point.get("score", 1.0)),
                )
            )

        requested_tests_raw = payload.get("requested_tests", [])
        if not isinstance(requested_tests_raw, list):
            raise TypeError(
                f"trend_direct requested_tests must be a list for {example.case_id}"
            )
        requested_tests = [str(item).lower() for item in requested_tests_raw]
        answer = rag._build_direct_trend_answer(
            structured_results=structured_results,
            requested_tests=requested_tests,
        )
        return answer

    raise ValueError(f"Unsupported task {task}")


def evaluate_examples(examples: list[EvalExample]) -> EvalRunResult:
    """Run all examples and collect policy accuracy metrics."""
    validator = EvidenceValidator()
    rag = _build_eval_rag_service()

    predictions: list[str] = []
    references: list[str] = []
    rows: list[dict[str, Any]] = []
    pass_count = 0

    for example in examples:
        prediction = _run_example(example=example, validator=validator, rag=rag)
        reference = example.expected
        passed = normalize_text(prediction) == normalize_text(reference)
        if passed:
            pass_count += 1
        predictions.append(prediction)
        references.append(reference)
        rows.append(
            {
                "id": example.case_id,
                "task": example.task,
                "prediction": prediction,
                "reference": reference,
                "passed": passed,
            }
        )

    return EvalRunResult(
        predictions=predictions,
        references=references,
        rows=rows,
        policy_pass_rate=pass_count / max(len(rows), 1),
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def write_outputs(
    *,
    output_dir: Path,
    scope: str,
    eval_file: Path,
    result: EvalRunResult,
) -> dict[str, Any]:
    """Write predictions and metrics artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "predictions.jsonl", result.rows)

    aggregate = compute_generation_metrics(result.predictions, result.references)
    task_metrics = compute_task_metrics(result)
    scope_metrics = {
        "exact_match": aggregate.exact_match,
        "contains_reference": aggregate.contains_reference,
        "token_f1": aggregate.token_f1,
        "fact_precision": aggregate.fact_precision,
        "fact_recall": aggregate.fact_recall,
        "hallucination_rate": aggregate.hallucination_rate,
        "policy_pass_rate": result.policy_pass_rate,
        "n_examples": aggregate.n_examples,
        "task_metrics": task_metrics,
    }
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "eval_file": str(eval_file),
        "metrics": {scope: scope_metrics},
    }
    (output_dir / "metrics_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    report = [
        "# RAG Hallucination Regression Report",
        "",
        f"- `eval_file`: {eval_file}",
        f"- `scope`: {scope}",
        f"- `n_examples`: {aggregate.n_examples}",
        "",
        "| metric | value |",
        "| --- | ---: |",
    ]
    for key in [
        "policy_pass_rate",
        "hallucination_rate",
        "fact_precision",
        "fact_recall",
        "token_f1",
        "exact_match",
    ]:
        report.append(f"| {key} | {scope_metrics[key]:.4f} |")
    report.extend(
        [
            "",
            "## Task Metrics",
            "",
            "| task | n_examples | policy_pass_rate | hallucination_rate | token_f1 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for task in sorted(task_metrics):
        metrics = task_metrics[task]
        report.append(
            f"| {task} | {metrics['n_examples']} | "
            f"{metrics['policy_pass_rate']:.4f} | "
            f"{metrics['hallucination_rate']:.4f} | "
            f"{metrics['token_f1']:.4f} |"
        )
    (output_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    args = parse_args()
    examples = load_eval_examples(args.eval_file)
    result = evaluate_examples(examples)
    summary = write_outputs(
        output_dir=args.output_dir,
        scope=args.scope,
        eval_file=args.eval_file,
        result=result,
    )
    scope_metrics = summary["metrics"][args.scope]
    print("RAG hallucination regression summary")
    print(f"- eval_file: {args.eval_file}")
    print(f"- output_dir: {args.output_dir}")
    print(f"- policy_pass_rate: {scope_metrics['policy_pass_rate']:.4f}")
    print(f"- hallucination_rate: {scope_metrics['hallucination_rate']:.4f}")
    print(f"- token_f1: {scope_metrics['token_f1']:.4f}")

    if scope_metrics["policy_pass_rate"] < args.min_policy_pass_rate:
        print(
            "Policy pass-rate below threshold: "
            f"{scope_metrics['policy_pass_rate']:.4f} < {args.min_policy_pass_rate:.4f}"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
