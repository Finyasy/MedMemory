from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.evaluate_retrieval_pipeline import (
    RetrievalOutcome,
    compute_aggregate_metrics,
    compute_subdomain_metrics,
    load_eval_examples,
    parse_k_values,
)


def test_parse_k_values_deduplicates_and_sorts():
    assert parse_k_values("10, 5,10,1") == [1, 5, 10]


def test_load_eval_examples_parses_expected_window(tmp_path: Path):
    payload = {
        "id": "case-1",
        "query": "What is my latest hemoglobin result?",
        "patient_id": 7,
        "subdomain": "labs",
        "gold_chunk_ids": [101, 102],
        "expected_source_types": ["lab_result"],
        "expected_time_window": {
            "date_from": "2026-01-01T00:00:00+00:00",
            "date_to": "2026-01-31T23:59:59+00:00",
        },
    }
    eval_file = tmp_path / "retrieval_eval.jsonl"
    eval_file.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    examples = load_eval_examples(eval_file)

    assert len(examples) == 1
    example = examples[0]
    assert example.case_id == "case-1"
    assert example.patient_id == 7
    assert example.gold_chunk_ids == [101, 102]
    assert example.expected_source_types == ["lab_result"]
    assert example.expected_date_from is not None
    assert example.expected_date_to is not None
    assert example.expected_date_from.tzinfo is not None
    assert example.expected_date_to.tzinfo is not None


def test_compute_aggregate_metrics_expected_values():
    outcomes = [
        RetrievalOutcome(
            case_id="c1",
            query="q1",
            patient_id=1,
            subdomain="labs",
            gold_chunk_ids=[10],
            retrieved_chunk_ids=[10, 11],
            first_relevant_rank=1,
            source_match_top1=True,
            source_match_at_k=True,
            time_match_top1=True,
            time_match_at_k=True,
            retrieval_time_ms=20.0,
            top_results=[],
            query_intent="value",
        ),
        RetrievalOutcome(
            case_id="c2",
            query="q2",
            patient_id=2,
            subdomain="medications",
            gold_chunk_ids=[20],
            retrieved_chunk_ids=[99, 20],
            first_relevant_rank=2,
            source_match_top1=False,
            source_match_at_k=False,
            time_match_top1=False,
            time_match_at_k=True,
            retrieval_time_ms=40.0,
            top_results=[],
            query_intent="status",
        ),
    ]

    metrics = compute_aggregate_metrics(outcomes, k_values=[1, 2])

    assert metrics["n_examples"] == 2
    assert metrics["recall@1"] == pytest.approx(0.5)
    assert metrics["recall@2"] == pytest.approx(1.0)
    assert metrics["mrr"] == pytest.approx(0.75)
    assert metrics["evidence_coverage_rate"] == pytest.approx(1.0)
    assert metrics["wrong_source_type_rate"] == pytest.approx(0.5)
    assert metrics["wrong_time_window_rate"] == pytest.approx(0.5)
    assert metrics["source_type_miss_rate@2"] == pytest.approx(0.5)
    assert metrics["time_window_miss_rate@2"] == pytest.approx(0.0)
    assert metrics["avg_retrieval_time_ms"] == pytest.approx(30.0)


def test_compute_subdomain_metrics_groups_rows():
    outcomes = [
        RetrievalOutcome(
            case_id="labs-1",
            query="q1",
            patient_id=1,
            subdomain="labs",
            gold_chunk_ids=[1],
            retrieved_chunk_ids=[1],
            first_relevant_rank=1,
            source_match_top1=True,
            source_match_at_k=True,
            time_match_top1=None,
            time_match_at_k=None,
            retrieval_time_ms=10.0,
            top_results=[],
            query_intent="value",
        ),
        RetrievalOutcome(
            case_id="meds-1",
            query="q2",
            patient_id=2,
            subdomain="medications",
            gold_chunk_ids=[2],
            retrieved_chunk_ids=[99],
            first_relevant_rank=None,
            source_match_top1=False,
            source_match_at_k=False,
            time_match_top1=None,
            time_match_at_k=None,
            retrieval_time_ms=30.0,
            top_results=[],
            query_intent="status",
        ),
    ]

    subdomains = compute_subdomain_metrics(outcomes, k_values=[1, 5, 10])

    assert set(subdomains.keys()) == {"labs", "medications"}
    assert subdomains["labs"]["recall@1"] == pytest.approx(1.0)
    assert subdomains["medications"]["recall@1"] == pytest.approx(0.0)
