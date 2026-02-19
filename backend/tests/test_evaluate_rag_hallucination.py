from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts.evaluate_rag_hallucination import (
    evaluate_examples,
    load_eval_examples,
    main,
    write_outputs,
)


def _eval_file() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "data"
        / "hallucination_rag_eval"
        / "eval.jsonl"
    )


def test_load_eval_examples_reads_repo_dataset():
    examples = load_eval_examples(_eval_file())

    assert len(examples) >= 10
    assert any(example.task == "numeric_grounding" for example in examples)
    assert any(example.task == "trend_direct" for example in examples)


def test_evaluate_examples_reaches_full_policy_pass_rate():
    examples = load_eval_examples(_eval_file())
    result = evaluate_examples(examples)

    assert result.policy_pass_rate == pytest.approx(1.0)
    assert len(result.rows) == len(examples)
    assert all(row["passed"] for row in result.rows)


def test_write_outputs_creates_gate_compatible_metrics(tmp_path: Path):
    examples = load_eval_examples(_eval_file())
    result = evaluate_examples(examples)
    summary = write_outputs(
        output_dir=tmp_path,
        scope="baseline",
        eval_file=_eval_file(),
        result=result,
    )

    metrics_file = tmp_path / "metrics_summary.json"
    report_file = tmp_path / "report.md"
    predictions_file = tmp_path / "predictions.jsonl"

    assert metrics_file.exists()
    assert report_file.exists()
    assert predictions_file.exists()

    payload = json.loads(metrics_file.read_text(encoding="utf-8"))
    baseline = payload["metrics"]["baseline"]
    assert baseline["hallucination_rate"] <= 0.05
    assert baseline["fact_precision"] >= 0.95
    assert baseline["fact_recall"] >= 0.95
    assert baseline["token_f1"] >= 0.95
    assert baseline["policy_pass_rate"] == pytest.approx(1.0)
    assert summary["metrics"]["baseline"]["policy_pass_rate"] == pytest.approx(1.0)


def test_main_returns_zero_and_writes_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate_rag_hallucination.py",
            "--eval-file",
            str(_eval_file()),
            "--output-dir",
            str(tmp_path),
        ],
    )

    exit_code = main()

    assert exit_code == 0
    assert (tmp_path / "metrics_summary.json").exists()
