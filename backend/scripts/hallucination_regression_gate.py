#!/usr/bin/env python3
"""Gate generation quality using hallucination-focused metrics.

This script is designed to consume `metrics_summary.json` files produced by
`scripts/evaluate_baseline_vs_qlora.py` and fail CI when key factuality metrics
regress beyond configured limits.

Example:
    cd backend
    uv run python scripts/hallucination_regression_gate.py \
      --candidate-metrics \
        artifacts/qlora_usecase_run/eval_compare/metrics_summary.json \
      --candidate-scope baseline \
      --baseline-metrics artifacts/hallucination_eval/baseline_metrics_summary.json \
      --baseline-scope baseline \
      --output-json artifacts/hallucination_eval/gate_report.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class GateThresholds:
    """Thresholds for absolute quality and regression checks."""

    max_hallucination_rate: float = 0.35
    min_fact_precision: float = 0.50
    min_fact_recall: float = 0.35
    min_token_f1: float = 0.35
    max_hallucination_increase: float = 0.03
    max_fact_precision_drop: float = 0.03
    max_fact_recall_drop: float = 0.05
    max_token_f1_drop: float = 0.03
    min_candidate_examples: int = 1
    min_baseline_examples: int = 1
    min_task_policy_pass_rate: dict[str, float] = field(default_factory=dict)
    min_task_examples: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class GateResult:
    """Result payload for programmatic/reporting consumption."""

    passed: bool
    failures: list[str]
    candidate_metrics: dict[str, float]
    candidate_n_examples: int
    baseline_metrics: dict[str, float] | None
    baseline_n_examples: int | None
    candidate_task_metrics: dict[str, dict[str, float | int]]
    baseline_task_metrics: dict[str, dict[str, float | int]] | None
    thresholds: GateThresholds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-metrics",
        type=Path,
        required=True,
        help="Path to candidate metrics_summary.json.",
    )
    parser.add_argument(
        "--candidate-scope",
        type=str,
        default="baseline",
        choices=["baseline", "finetuned"],
        help="Metric scope from the candidate file to gate.",
    )
    parser.add_argument(
        "--baseline-metrics",
        type=Path,
        default=None,
        help="Optional historical baseline metrics_summary.json for regression checks.",
    )
    parser.add_argument(
        "--baseline-scope",
        type=str,
        default=None,
        choices=["baseline", "finetuned"],
        help="Metric scope from baseline file (defaults to candidate scope).",
    )
    parser.add_argument("--max-hallucination-rate", type=float, default=0.35)
    parser.add_argument("--min-fact-precision", type=float, default=0.50)
    parser.add_argument("--min-fact-recall", type=float, default=0.35)
    parser.add_argument("--min-token-f1", type=float, default=0.35)
    parser.add_argument("--max-hallucination-increase", type=float, default=0.03)
    parser.add_argument("--max-fact-precision-drop", type=float, default=0.03)
    parser.add_argument("--max-fact-recall-drop", type=float, default=0.05)
    parser.add_argument("--max-token-f1-drop", type=float, default=0.03)
    parser.add_argument("--min-candidate-examples", type=int, default=1)
    parser.add_argument("--min-baseline-examples", type=int, default=1)
    parser.add_argument(
        "--min-task-policy-pass-rate",
        action="append",
        default=None,
        help=(
            "Task-specific minimum policy pass-rate rule in task=value format. "
            "Repeat for multiple tasks."
        ),
    )
    parser.add_argument(
        "--min-task-examples",
        action="append",
        default=None,
        help=(
            "Task-specific minimum example count rule in task=value format. "
            "Repeat for multiple tasks."
        ),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional report output path.",
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Print failures but exit 0 (for dry runs).",
    )
    return parser.parse_args()


def _coerce_float(metrics: dict[str, Any], key: str) -> float:
    if key not in metrics:
        raise KeyError(f"Missing required metric: {key}")
    value = metrics[key]
    if isinstance(value, (int, float)):
        return float(value)
    raise TypeError(f"Metric '{key}' must be numeric, got {type(value).__name__}.")


def _coerce_int(metrics: dict[str, Any], key: str) -> int:
    if key not in metrics:
        raise KeyError(f"Missing required metric: {key}")
    value = metrics[key]
    if isinstance(value, int):
        return value
    raise TypeError(f"Metric '{key}' must be an integer, got {type(value).__name__}.")


def _parse_task_float_rules(
    values: list[str] | None,
    *,
    flag_name: str,
) -> dict[str, float]:
    if not values:
        return {}
    parsed: dict[str, float] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"{flag_name} expects task=value, got '{value}'")
        task, raw_threshold = value.split("=", 1)
        task_name = task.strip()
        if not task_name:
            raise ValueError(f"{flag_name} task cannot be empty: '{value}'")
        try:
            threshold = float(raw_threshold)
        except ValueError as exc:
            raise ValueError(
                f"{flag_name} value for task '{task_name}' must be numeric: "
                f"'{raw_threshold}'"
            ) from exc
        parsed[task_name] = threshold
    return parsed


def _parse_task_int_rules(
    values: list[str] | None,
    *,
    flag_name: str,
) -> dict[str, int]:
    if not values:
        return {}
    parsed: dict[str, int] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"{flag_name} expects task=value, got '{value}'")
        task, raw_threshold = value.split("=", 1)
        task_name = task.strip()
        if not task_name:
            raise ValueError(f"{flag_name} task cannot be empty: '{value}'")
        try:
            threshold = int(raw_threshold)
        except ValueError as exc:
            raise ValueError(
                f"{flag_name} value for task '{task_name}' must be an integer: "
                f"'{raw_threshold}'"
            ) from exc
        parsed[task_name] = threshold
    return parsed


def extract_metrics(path: Path, scope: str) -> dict[str, float]:
    """Extract required metrics from a summary file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics_root = payload.get("metrics", payload)

    scoped = metrics_root.get(scope, None)
    if scoped is None:
        available = (
            sorted(metrics_root.keys())
            if isinstance(metrics_root, dict)
            else ["<invalid>"]
        )
        raise KeyError(f"Scope '{scope}' not found in {path}. Available: {available}")

    required = [
        "hallucination_rate",
        "fact_precision",
        "fact_recall",
        "token_f1",
    ]
    result: dict[str, float] = {}
    for key in required:
        result[key] = _coerce_float(scoped, key)
    return result


def extract_n_examples(path: Path, scope: str) -> int:
    """Extract n_examples from a summary file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics_root = payload.get("metrics", payload)
    scoped = metrics_root.get(scope, None)
    if scoped is None:
        available = (
            sorted(metrics_root.keys())
            if isinstance(metrics_root, dict)
            else ["<invalid>"]
        )
        raise KeyError(f"Scope '{scope}' not found in {path}. Available: {available}")
    return _coerce_int(scoped, "n_examples")


def extract_task_metrics(path: Path, scope: str) -> dict[str, dict[str, float | int]]:
    """Extract optional per-task metrics from a summary file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics_root = payload.get("metrics", payload)
    scoped = metrics_root.get(scope, None)
    if scoped is None:
        available = (
            sorted(metrics_root.keys())
            if isinstance(metrics_root, dict)
            else ["<invalid>"]
        )
        raise KeyError(f"Scope '{scope}' not found in {path}. Available: {available}")

    task_metrics_raw = scoped.get("task_metrics", {})
    if task_metrics_raw is None:
        return {}
    if not isinstance(task_metrics_raw, dict):
        raise TypeError(f"task_metrics in {path} scope '{scope}' must be an object.")

    result: dict[str, dict[str, float | int]] = {}
    for task_name, task_payload in task_metrics_raw.items():
        if not isinstance(task_payload, dict):
            raise TypeError(f"task_metrics['{task_name}'] in {path} must be an object.")
        parsed_task: dict[str, float | int] = {
            "policy_pass_rate": _coerce_float(task_payload, "policy_pass_rate"),
            "n_examples": _coerce_int(task_payload, "n_examples"),
        }
        for optional_key in [
            "exact_match",
            "token_f1",
            "fact_precision",
            "fact_recall",
            "hallucination_rate",
        ]:
            if optional_key in task_payload:
                parsed_task[optional_key] = _coerce_float(task_payload, optional_key)
        result[str(task_name)] = parsed_task
    return result


def evaluate_gate(
    *,
    candidate_metrics: dict[str, float],
    candidate_n_examples: int,
    candidate_task_metrics: dict[str, dict[str, float | int]] | None,
    thresholds: GateThresholds,
    baseline_metrics: dict[str, float] | None = None,
    baseline_n_examples: int | None = None,
    baseline_task_metrics: dict[str, dict[str, float | int]] | None = None,
) -> GateResult:
    """Evaluate absolute and regression gate checks."""
    failures: list[str] = []

    if candidate_n_examples < thresholds.min_candidate_examples:
        failures.append(
            "n_examples "
            f"{candidate_n_examples} below minimum "
            f"{thresholds.min_candidate_examples}"
        )

    candidate_task_metrics = candidate_task_metrics or {}
    for task, min_rate in sorted(thresholds.min_task_policy_pass_rate.items()):
        task_payload = candidate_task_metrics.get(task)
        if task_payload is None:
            failures.append(f"missing task_metrics for task '{task}'")
            continue
        rate_value = task_payload.get("policy_pass_rate")
        if not isinstance(rate_value, (int, float)):
            failures.append(f"task '{task}' missing numeric policy_pass_rate")
            continue
        if float(rate_value) < min_rate:
            failures.append(
                "task_policy_pass_rate "
                f"{task}={float(rate_value):.4f} below {min_rate:.4f}"
            )

    for task, min_examples in sorted(thresholds.min_task_examples.items()):
        task_payload = candidate_task_metrics.get(task)
        if task_payload is None:
            failures.append(f"missing task_metrics for task '{task}'")
            continue
        n_value = task_payload.get("n_examples")
        if not isinstance(n_value, int):
            failures.append(f"task '{task}' missing integer n_examples")
            continue
        if n_value < min_examples:
            failures.append(
                f"task_n_examples {task}={n_value} below minimum {min_examples}"
            )

    if candidate_metrics["hallucination_rate"] > thresholds.max_hallucination_rate:
        failures.append(
            "hallucination_rate "
            f"{candidate_metrics['hallucination_rate']:.4f} exceeds "
            f"{thresholds.max_hallucination_rate:.4f}"
        )
    if candidate_metrics["fact_precision"] < thresholds.min_fact_precision:
        failures.append(
            "fact_precision "
            f"{candidate_metrics['fact_precision']:.4f} below "
            f"{thresholds.min_fact_precision:.4f}"
        )
    if candidate_metrics["fact_recall"] < thresholds.min_fact_recall:
        failures.append(
            "fact_recall "
            f"{candidate_metrics['fact_recall']:.4f} below "
            f"{thresholds.min_fact_recall:.4f}"
        )
    if candidate_metrics["token_f1"] < thresholds.min_token_f1:
        failures.append(
            "token_f1 "
            f"{candidate_metrics['token_f1']:.4f} below "
            f"{thresholds.min_token_f1:.4f}"
        )

    if baseline_metrics is not None:
        hallucination_delta = (
            candidate_metrics["hallucination_rate"]
            - baseline_metrics["hallucination_rate"]
        )
        if hallucination_delta > thresholds.max_hallucination_increase:
            failures.append(
                "hallucination_rate regression "
                f"+{hallucination_delta:.4f} exceeds "
                f"+{thresholds.max_hallucination_increase:.4f}"
            )

        fact_precision_drop = (
            baseline_metrics["fact_precision"] - candidate_metrics["fact_precision"]
        )
        if fact_precision_drop > thresholds.max_fact_precision_drop:
            failures.append(
                "fact_precision regression "
                f"-{fact_precision_drop:.4f} exceeds "
                f"-{thresholds.max_fact_precision_drop:.4f}"
            )

        fact_recall_drop = (
            baseline_metrics["fact_recall"] - candidate_metrics["fact_recall"]
        )
        if fact_recall_drop > thresholds.max_fact_recall_drop:
            failures.append(
                "fact_recall regression "
                f"-{fact_recall_drop:.4f} exceeds "
                f"-{thresholds.max_fact_recall_drop:.4f}"
            )

        token_f1_drop = baseline_metrics["token_f1"] - candidate_metrics["token_f1"]
        if token_f1_drop > thresholds.max_token_f1_drop:
            failures.append(
                "token_f1 regression "
                f"-{token_f1_drop:.4f} exceeds "
                f"-{thresholds.max_token_f1_drop:.4f}"
            )
        if (
            baseline_n_examples is not None
            and baseline_n_examples < thresholds.min_baseline_examples
        ):
            failures.append(
                "baseline_n_examples "
                f"{baseline_n_examples} below minimum "
                f"{thresholds.min_baseline_examples}"
            )

    return GateResult(
        passed=not failures,
        failures=failures,
        candidate_metrics=candidate_metrics,
        candidate_n_examples=candidate_n_examples,
        baseline_metrics=baseline_metrics,
        baseline_n_examples=baseline_n_examples,
        candidate_task_metrics=candidate_task_metrics,
        baseline_task_metrics=baseline_task_metrics,
        thresholds=thresholds,
    )


def print_report(result: GateResult) -> None:
    print("Hallucination Gate Report")
    print("-------------------------")
    print("candidate_metrics:")
    print(f"- n_examples: {result.candidate_n_examples}")
    for key, value in result.candidate_metrics.items():
        print(f"- {key}: {value:.4f}")
    if result.baseline_metrics is not None:
        print("baseline_metrics:")
        if result.baseline_n_examples is not None:
            print(f"- n_examples: {result.baseline_n_examples}")
        for key, value in result.baseline_metrics.items():
            print(f"- {key}: {value:.4f}")
    if result.candidate_task_metrics:
        print("candidate_task_metrics:")
        for task in sorted(result.candidate_task_metrics):
            task_payload = result.candidate_task_metrics[task]
            n_examples = task_payload.get("n_examples")
            policy_pass_rate = task_payload.get("policy_pass_rate")
            rate_text = (
                f"{float(policy_pass_rate):.4f}"
                if isinstance(policy_pass_rate, (int, float))
                else "n/a"
            )
            print(f"- {task}: n_examples={n_examples}, policy_pass_rate={rate_text}")
    if result.baseline_task_metrics:
        print("baseline_task_metrics:")
        for task in sorted(result.baseline_task_metrics):
            task_payload = result.baseline_task_metrics[task]
            n_examples = task_payload.get("n_examples")
            policy_pass_rate = task_payload.get("policy_pass_rate")
            rate_text = (
                f"{float(policy_pass_rate):.4f}"
                if isinstance(policy_pass_rate, (int, float))
                else "n/a"
            )
            print(f"- {task}: n_examples={n_examples}, policy_pass_rate={rate_text}")
    if result.passed:
        print("status: PASS")
    else:
        print("status: FAIL")
        for failure in result.failures:
            print(f"- {failure}")


def write_report(path: Path, result: GateResult, args: argparse.Namespace) -> None:
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "candidate_metrics_file": str(args.candidate_metrics),
        "candidate_scope": args.candidate_scope,
        "baseline_metrics_file": (
            str(args.baseline_metrics) if args.baseline_metrics else None
        ),
        "baseline_scope": args.baseline_scope,
        "result": {
            "passed": result.passed,
            "failures": result.failures,
            "candidate_metrics": result.candidate_metrics,
            "candidate_n_examples": result.candidate_n_examples,
            "candidate_task_metrics": result.candidate_task_metrics,
            "baseline_metrics": result.baseline_metrics,
            "baseline_n_examples": result.baseline_n_examples,
            "baseline_task_metrics": result.baseline_task_metrics,
            "thresholds": asdict(result.thresholds),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> int:
    args = parse_args()
    baseline_scope = args.baseline_scope or args.candidate_scope

    try:
        min_task_policy_pass_rate = _parse_task_float_rules(
            args.min_task_policy_pass_rate,
            flag_name="--min-task-policy-pass-rate",
        )
        min_task_examples = _parse_task_int_rules(
            args.min_task_examples,
            flag_name="--min-task-examples",
        )
    except ValueError as exc:
        print(f"error: {exc}")
        return 2

    thresholds = GateThresholds(
        max_hallucination_rate=args.max_hallucination_rate,
        min_fact_precision=args.min_fact_precision,
        min_fact_recall=args.min_fact_recall,
        min_token_f1=args.min_token_f1,
        max_hallucination_increase=args.max_hallucination_increase,
        max_fact_precision_drop=args.max_fact_precision_drop,
        max_fact_recall_drop=args.max_fact_recall_drop,
        max_token_f1_drop=args.max_token_f1_drop,
        min_candidate_examples=args.min_candidate_examples,
        min_baseline_examples=args.min_baseline_examples,
        min_task_policy_pass_rate=min_task_policy_pass_rate,
        min_task_examples=min_task_examples,
    )

    candidate_metrics = extract_metrics(args.candidate_metrics, args.candidate_scope)
    candidate_n_examples = extract_n_examples(
        args.candidate_metrics, args.candidate_scope
    )
    candidate_task_metrics = extract_task_metrics(
        args.candidate_metrics, args.candidate_scope
    )
    baseline_metrics = None
    baseline_n_examples = None
    baseline_task_metrics = None
    if args.baseline_metrics:
        baseline_metrics = extract_metrics(args.baseline_metrics, baseline_scope)
        baseline_n_examples = extract_n_examples(args.baseline_metrics, baseline_scope)
        baseline_task_metrics = extract_task_metrics(
            args.baseline_metrics, baseline_scope
        )

    result = evaluate_gate(
        candidate_metrics=candidate_metrics,
        candidate_n_examples=candidate_n_examples,
        candidate_task_metrics=candidate_task_metrics,
        baseline_metrics=baseline_metrics,
        baseline_n_examples=baseline_n_examples,
        baseline_task_metrics=baseline_task_metrics,
        thresholds=thresholds,
    )

    print_report(result)
    if args.output_json:
        write_report(args.output_json, result, args)
        print(f"wrote report: {args.output_json}")

    if result.passed or args.warn_only:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
