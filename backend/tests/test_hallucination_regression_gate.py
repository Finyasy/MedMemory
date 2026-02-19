from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts.hallucination_regression_gate import (
    GateThresholds,
    evaluate_gate,
    extract_metrics,
    extract_n_examples,
    extract_task_metrics,
    main,
)


def _write_metrics_summary(
    path: Path,
    *,
    baseline: dict[str, float],
    finetuned: dict[str, float] | None = None,
) -> None:
    payload: dict[str, object] = {"metrics": {"baseline": baseline}}
    if finetuned is not None:
        payload["metrics"]["finetuned"] = finetuned
    path.write_text(json.dumps(payload), encoding="utf-8")


def _metrics(
    *,
    hallucination_rate: float,
    fact_precision: float,
    fact_recall: float,
    token_f1: float,
    n_examples: int = 1,
) -> dict[str, float]:
    return {
        "n_examples": n_examples,
        "hallucination_rate": hallucination_rate,
        "fact_precision": fact_precision,
        "fact_recall": fact_recall,
        "token_f1": token_f1,
    }


def _task_metrics(
    *,
    n_examples: int,
    policy_pass_rate: float,
) -> dict[str, float | int]:
    return {
        "n_examples": n_examples,
        "policy_pass_rate": policy_pass_rate,
        "exact_match": policy_pass_rate,
        "token_f1": policy_pass_rate,
        "fact_precision": policy_pass_rate,
        "fact_recall": policy_pass_rate,
        "hallucination_rate": 0.0,
    }


def test_extract_metrics_reads_scope_from_summary_file(tmp_path: Path):
    metrics_file = tmp_path / "metrics_summary.json"
    baseline = _metrics(
        hallucination_rate=0.20,
        fact_precision=0.68,
        fact_recall=0.61,
        token_f1=0.64,
    )
    finetuned = _metrics(
        hallucination_rate=0.17,
        fact_precision=0.71,
        fact_recall=0.66,
        token_f1=0.69,
    )
    _write_metrics_summary(metrics_file, baseline=baseline, finetuned=finetuned)

    parsed = extract_metrics(metrics_file, "finetuned")

    assert parsed == {
        "hallucination_rate": finetuned["hallucination_rate"],
        "fact_precision": finetuned["fact_precision"],
        "fact_recall": finetuned["fact_recall"],
        "token_f1": finetuned["token_f1"],
    }


def test_extract_metrics_raises_on_missing_scope(tmp_path: Path):
    metrics_file = tmp_path / "metrics_summary.json"
    _write_metrics_summary(
        metrics_file,
        baseline=_metrics(
            hallucination_rate=0.19,
            fact_precision=0.70,
            fact_recall=0.60,
            token_f1=0.65,
        ),
    )

    with pytest.raises(KeyError, match="Scope 'finetuned'"):
        extract_metrics(metrics_file, "finetuned")


def test_extract_n_examples_reads_scope(tmp_path: Path):
    metrics_file = tmp_path / "metrics_summary.json"
    _write_metrics_summary(
        metrics_file,
        baseline={
            **_metrics(
                hallucination_rate=0.20,
                fact_precision=0.68,
                fact_recall=0.61,
                token_f1=0.64,
            ),
            "n_examples": 17,
        },
    )

    assert extract_n_examples(metrics_file, "baseline") == 17


def test_extract_task_metrics_reads_scope(tmp_path: Path):
    metrics_file = tmp_path / "metrics_summary.json"
    payload = {
        "metrics": {
            "baseline": {
                **_metrics(
                    hallucination_rate=0.20,
                    fact_precision=0.68,
                    fact_recall=0.61,
                    token_f1=0.64,
                    n_examples=12,
                ),
                "task_metrics": {
                    "numeric_citation": _task_metrics(
                        n_examples=4,
                        policy_pass_rate=1.0,
                    )
                },
            }
        }
    }
    metrics_file.write_text(json.dumps(payload), encoding="utf-8")

    parsed = extract_task_metrics(metrics_file, "baseline")

    assert parsed["numeric_citation"]["n_examples"] == 4
    assert parsed["numeric_citation"]["policy_pass_rate"] == pytest.approx(1.0)


def test_evaluate_gate_fails_absolute_thresholds():
    candidate = _metrics(
        hallucination_rate=0.45,
        fact_precision=0.40,
        fact_recall=0.31,
        token_f1=0.25,
    )

    result = evaluate_gate(
        candidate_metrics=candidate,
        candidate_n_examples=20,
        candidate_task_metrics={},
        thresholds=GateThresholds(),
    )

    assert result.passed is False
    assert any("hallucination_rate" in failure for failure in result.failures)
    assert any("fact_precision" in failure for failure in result.failures)
    assert any("fact_recall" in failure for failure in result.failures)
    assert any("token_f1" in failure for failure in result.failures)


def test_evaluate_gate_detects_regressions_vs_baseline():
    baseline = _metrics(
        hallucination_rate=0.12,
        fact_precision=0.80,
        fact_recall=0.72,
        token_f1=0.71,
    )
    candidate = _metrics(
        hallucination_rate=0.20,
        fact_precision=0.74,
        fact_recall=0.66,
        token_f1=0.66,
    )

    result = evaluate_gate(
        candidate_metrics=candidate,
        candidate_n_examples=20,
        candidate_task_metrics={},
        baseline_metrics=baseline,
        baseline_n_examples=20,
        baseline_task_metrics={},
        thresholds=GateThresholds(),
    )

    assert result.passed is False
    assert any(
        "hallucination_rate regression" in failure for failure in result.failures
    )
    assert any("fact_precision regression" in failure for failure in result.failures)
    assert any("fact_recall regression" in failure for failure in result.failures)
    assert any("token_f1 regression" in failure for failure in result.failures)


def test_main_warn_only_exits_zero_and_writes_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    metrics_file = tmp_path / "metrics_summary.json"
    report_file = tmp_path / "gate_report.json"
    _write_metrics_summary(
        metrics_file,
        baseline=_metrics(
            hallucination_rate=0.50,
            fact_precision=0.35,
            fact_recall=0.30,
            token_f1=0.20,
        ),
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hallucination_regression_gate.py",
            "--candidate-metrics",
            str(metrics_file),
            "--output-json",
            str(report_file),
            "--warn-only",
        ],
    )

    exit_code = main()

    assert exit_code == 0
    payload = json.loads(report_file.read_text(encoding="utf-8"))
    assert payload["result"]["passed"] is False
    assert payload["result"]["candidate_metrics"][
        "hallucination_rate"
    ] == pytest.approx(0.50)


def test_evaluate_gate_fails_when_too_few_examples():
    candidate = _metrics(
        hallucination_rate=0.05,
        fact_precision=0.95,
        fact_recall=0.95,
        token_f1=0.95,
    )
    result = evaluate_gate(
        candidate_metrics=candidate,
        candidate_n_examples=2,
        candidate_task_metrics={},
        thresholds=GateThresholds(min_candidate_examples=5),
    )

    assert result.passed is False
    assert any("n_examples" in failure for failure in result.failures)


def test_evaluate_gate_fails_task_thresholds():
    candidate = _metrics(
        hallucination_rate=0.0,
        fact_precision=1.0,
        fact_recall=1.0,
        token_f1=1.0,
    )
    candidate_task_metrics = {
        "numeric_citation": _task_metrics(n_examples=3, policy_pass_rate=0.66)
    }
    thresholds = GateThresholds(
        min_task_policy_pass_rate={"numeric_citation": 1.0},
        min_task_examples={"numeric_citation": 4},
    )
    result = evaluate_gate(
        candidate_metrics=candidate,
        candidate_n_examples=20,
        candidate_task_metrics=candidate_task_metrics,
        thresholds=thresholds,
    )

    assert result.passed is False
    assert any("task_policy_pass_rate" in failure for failure in result.failures)
    assert any("task_n_examples" in failure for failure in result.failures)


def test_repo_baseline_snapshot_passes_ci_gate_thresholds():
    metrics_file = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "hallucination_eval"
        / "baseline_metrics_summary.json"
    )
    metrics = extract_metrics(metrics_file, "baseline")
    n_examples = extract_n_examples(metrics_file, "baseline")
    task_metrics = extract_task_metrics(metrics_file, "baseline")
    thresholds = GateThresholds(
        max_hallucination_rate=0.01,
        min_fact_precision=0.99,
        min_fact_recall=0.99,
        min_token_f1=0.99,
        max_hallucination_increase=0.01,
        max_fact_precision_drop=0.01,
        max_fact_recall_drop=0.01,
        max_token_f1_drop=0.01,
        min_candidate_examples=22,
        min_baseline_examples=22,
        min_task_policy_pass_rate={
            "numeric_grounding": 1.0,
            "numeric_citation": 1.0,
            "question_mode": 1.0,
            "context_gate": 1.0,
            "trend_direct": 1.0,
        },
        min_task_examples={
            "numeric_grounding": 4,
            "numeric_citation": 4,
            "question_mode": 4,
            "context_gate": 5,
            "trend_direct": 5,
        },
    )

    result = evaluate_gate(
        candidate_metrics=metrics,
        candidate_n_examples=n_examples,
        candidate_task_metrics=task_metrics,
        baseline_metrics=metrics,
        baseline_n_examples=n_examples,
        baseline_task_metrics=task_metrics,
        thresholds=thresholds,
    )

    assert result.passed is True
