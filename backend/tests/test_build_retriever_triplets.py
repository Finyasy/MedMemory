from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.build_retriever_triplets import (
    build_triplet_datasets,
    load_rerank_rows,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def test_load_rerank_rows_reads_and_normalizes(tmp_path: Path):
    input_file = tmp_path / "rerank.jsonl"
    _write_jsonl(
        input_file,
        [
            {
                "id": "a",
                "group_id": "g1",
                "query": "  What is my latest A1c? ",
                "label": 1,
                "chunk_text": " A1c was 7.2% ",
                "subdomain": "labs",
            },
            {
                "id": "b",
                "group_id": "g1",
                "query": "What is my latest A1c?",
                "label": 0,
                "chunk_text": "Unrelated chunk",
                "hard_negative": True,
            },
        ],
    )

    rows = load_rerank_rows(input_file)

    assert len(rows) == 2
    assert rows[0].query == "What is my latest A1c?"
    assert rows[0].chunk_text == "A1c was 7.2%"
    assert rows[1].hard_negative is True


def test_build_triplet_datasets_generates_train_and_eval(tmp_path: Path):
    input_file = tmp_path / "rerank.jsonl"
    output_dir = tmp_path / "triplets"
    _write_jsonl(
        input_file,
        [
            # group 1
            {
                "id": "g1_pos",
                "group_id": "g1",
                "query": "What is my latest hemoglobin?",
                "patient_id": 1,
                "subdomain": "labs",
                "label": 1,
                "chunk_id": 10,
                "chunk_text": "Hemoglobin 10.1 g/dL",
                "chunk_source_type": "lab_result",
            },
            {
                "id": "g1_neg_hard",
                "group_id": "g1",
                "query": "What is my latest hemoglobin?",
                "patient_id": 1,
                "subdomain": "labs",
                "label": 0,
                "hard_negative": True,
                "chunk_id": 11,
                "chunk_text": "Hemoglobin not recorded",
                "chunk_source_type": "document",
            },
            {
                "id": "g1_neg_easy",
                "group_id": "g1",
                "query": "What is my latest hemoglobin?",
                "patient_id": 1,
                "subdomain": "labs",
                "label": 0,
                "hard_negative": False,
                "chunk_id": 12,
                "chunk_text": "Medication note",
                "chunk_source_type": "medication",
            },
            # group 2
            {
                "id": "g2_pos",
                "group_id": "g2",
                "query": "Is metformin active?",
                "patient_id": 2,
                "subdomain": "medications",
                "label": 1,
                "chunk_id": 20,
                "chunk_text": "Metformin active daily",
                "chunk_source_type": "medication",
            },
            {
                "id": "g2_neg",
                "group_id": "g2",
                "query": "Is metformin active?",
                "patient_id": 2,
                "subdomain": "medications",
                "label": 0,
                "chunk_id": 21,
                "chunk_text": "Old discharge summary",
                "chunk_source_type": "document",
            },
        ],
    )

    args = SimpleNamespace(
        eval_ratio=0.5,
        min_eval_queries=1,
        max_triplets_per_query=8,
        negatives_per_positive=2,
        prefer_hard_negatives=True,
        seed=42,
        input_file=input_file,
        output_dir=output_dir,
    )

    summary = build_triplet_datasets(args)

    assert (output_dir / "train_triplets.jsonl").exists()
    assert (output_dir / "eval_triplets.jsonl").exists()
    assert summary["counts"]["n_train_triplets"] >= 1
    assert summary["counts"]["n_eval_triplets"] >= 1
