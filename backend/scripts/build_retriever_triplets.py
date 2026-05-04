#!/usr/bin/env python3
"""Build bi-encoder triplet datasets from reranker supervision rows.

Input:
  - data/rag_benchmark/rerank_train.jsonl

Outputs:
  - data/retriever_triplets/train_triplets.jsonl
  - data/retriever_triplets/eval_triplets.jsonl
  - data/retriever_triplets/summary.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RerankRow:
    """Single row from rerank_train.jsonl."""

    row_id: str
    group_id: str
    query: str
    patient_id: int | None
    subdomain: str
    label: int
    hard_negative: bool
    chunk_id: int | None
    chunk_text: str
    chunk_source_type: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-file",
        type=Path,
        default=Path("data/rag_benchmark/rerank_train.jsonl"),
        help="Input rerank supervision JSONL file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/retriever_triplets"),
        help="Directory where train/eval triplet JSONL files are written.",
    )
    parser.add_argument(
        "--eval-ratio",
        type=float,
        default=0.15,
        help="Eval split ratio.",
    )
    parser.add_argument(
        "--min-eval-queries",
        type=int,
        default=20,
        help="Minimum number of eval query groups when data volume allows.",
    )
    parser.add_argument(
        "--max-triplets-per-query",
        type=int,
        default=24,
        help="Cap generated triplets per query group.",
    )
    parser.add_argument(
        "--negatives-per-positive",
        type=int,
        default=2,
        help="Negatives sampled for each positive chunk.",
    )
    parser.add_argument(
        "--prefer-hard-negatives",
        action="store_true",
        help="Prefer hard negatives before random negatives.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed.",
    )
    return parser.parse_args()


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def _stable_triplet_id(
    *,
    group_id: str,
    query: str,
    positive_chunk_id: int | None,
    negative_chunk_id: int | None,
) -> str:
    digest = hashlib.sha1(
        f"{group_id}|{query}|{positive_chunk_id}|{negative_chunk_id}".encode()
    ).hexdigest()[:16]
    return f"triplet_{digest}"


def load_rerank_rows(path: Path) -> list[RerankRow]:
    """Load rerank supervision JSONL rows."""
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    rows: list[RerankRow] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        query = _normalize_text(str(payload.get("query", "")))
        if not query:
            raise ValueError(f"Missing query on line {idx}.")
        label = int(payload.get("label", 0))
        if label not in (0, 1):
            raise ValueError(f"label must be 0 or 1 on line {idx}.")
        group_id = str(payload.get("group_id") or payload.get("id") or f"group-{idx}")
        chunk_text = _normalize_text(str(payload.get("chunk_text", "")))
        if not chunk_text:
            continue
        rows.append(
            RerankRow(
                row_id=str(payload.get("id") or f"row-{idx}"),
                group_id=group_id,
                query=query,
                patient_id=(
                    int(payload["patient_id"])
                    if payload.get("patient_id") is not None
                    else None
                ),
                subdomain=str(payload.get("subdomain", "unknown")),
                label=label,
                hard_negative=bool(payload.get("hard_negative", False)),
                chunk_id=(
                    int(payload["chunk_id"])
                    if payload.get("chunk_id") is not None
                    else None
                ),
                chunk_text=chunk_text,
                chunk_source_type=(
                    str(payload.get("chunk_source_type"))
                    if payload.get("chunk_source_type") is not None
                    else None
                ),
            )
        )
    if not rows:
        raise ValueError(f"No valid rerank rows found in {path}")
    return rows


def group_rows(rows: list[RerankRow]) -> dict[str, list[RerankRow]]:
    grouped: dict[str, list[RerankRow]] = defaultdict(list)
    for row in rows:
        grouped[row.group_id].append(row)
    return grouped


def split_group_ids(
    group_ids: list[str],
    *,
    grouped_rows: dict[str, list[RerankRow]],
    eval_ratio: float,
    min_eval_queries: int,
    seed: int,
) -> tuple[set[str], set[str], str]:
    rng = random.Random(seed)
    ids = list(group_ids)
    rng.shuffle(ids)

    if not ids:
        return set(), set(), "empty"
    if len(ids) == 1:
        only = {ids[0]}
        return only, only, "single_group_overlap"

    patient_to_groups: dict[int | None, set[str]] = defaultdict(set)
    for group_id in ids:
        patient_id = grouped_rows[group_id][0].patient_id if grouped_rows[group_id] else None
        patient_to_groups[patient_id].add(group_id)

    patient_ids = [pid for pid in patient_to_groups if pid is not None]
    if len(patient_ids) >= 2:
        rng.shuffle(patient_ids)
        eval_patient_n = max(1, int(round(len(patient_ids) * eval_ratio)))
        eval_patient_n = min(eval_patient_n, len(patient_ids) - 1)
        eval_patients = set(patient_ids[:eval_patient_n])
        eval_ids = {
            group_id
            for patient_id in eval_patients
            for group_id in patient_to_groups[patient_id]
        }
        train_ids = set(ids) - eval_ids
        if eval_ids and train_ids:
            return train_ids, eval_ids, "patient_level"

    eval_n = max(1, int(round(len(ids) * eval_ratio)))
    if len(ids) >= min_eval_queries * 2:
        eval_n = max(eval_n, min_eval_queries)
    eval_n = min(eval_n, len(ids) - 1)
    eval_ids = set(ids[:eval_n])
    train_ids = set(ids[eval_n:])
    return train_ids, eval_ids, "group_level"


def _pick_negative_pool(
    negatives: list[RerankRow],
    *,
    prefer_hard_negatives: bool,
) -> list[RerankRow]:
    if not prefer_hard_negatives:
        return negatives
    hard = [row for row in negatives if row.hard_negative]
    easy = [row for row in negatives if not row.hard_negative]
    return hard + easy


def build_triplet_rows(
    grouped_rows: dict[str, list[RerankRow]],
    allowed_group_ids: set[str],
    *,
    negatives_per_positive: int,
    max_triplets_per_query: int,
    prefer_hard_negatives: bool,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, int | None, int | None]] = set()

    for group_id in sorted(allowed_group_ids):
        group = grouped_rows.get(group_id, [])
        if not group:
            continue
        positives = [row for row in group if row.label == 1]
        negatives = [row for row in group if row.label == 0]
        if not positives or not negatives:
            continue

        negative_pool = _pick_negative_pool(
            negatives,
            prefer_hard_negatives=prefer_hard_negatives,
        )

        group_triplets = 0
        for positive in positives:
            if group_triplets >= max_triplets_per_query:
                break

            if len(negative_pool) <= negatives_per_positive:
                sampled_negatives = list(negative_pool)
            else:
                sampled_negatives = rng.sample(negative_pool, k=negatives_per_positive)

            for negative in sampled_negatives:
                key = (group_id, positive.chunk_id, negative.chunk_id)
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                row = {
                    "id": _stable_triplet_id(
                        group_id=group_id,
                        query=positive.query,
                        positive_chunk_id=positive.chunk_id,
                        negative_chunk_id=negative.chunk_id,
                    ),
                    "group_id": group_id,
                    "query": positive.query,
                    "anchor": positive.query,
                    "positive": positive.chunk_text,
                    "negative": negative.chunk_text,
                    "patient_id": positive.patient_id,
                    "subdomain": positive.subdomain,
                    "positive_chunk_id": positive.chunk_id,
                    "negative_chunk_id": negative.chunk_id,
                    "positive_source_type": positive.chunk_source_type,
                    "negative_source_type": negative.chunk_source_type,
                    "negative_hard": negative.hard_negative,
                }
                rows.append(row)
                group_triplets += 1
                if group_triplets >= max_triplets_per_query:
                    break

    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True))
            handle.write("\n")


def _count_by_subdomain(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.get("subdomain", "unknown"))] += 1
    return dict(sorted(counts.items()))


def build_triplet_datasets(args: argparse.Namespace) -> dict[str, Any]:
    if not (0.05 <= args.eval_ratio <= 0.5):
        raise ValueError("--eval-ratio must be between 0.05 and 0.5.")
    if args.negatives_per_positive <= 0:
        raise ValueError("--negatives-per-positive must be > 0.")
    if args.max_triplets_per_query <= 0:
        raise ValueError("--max-triplets-per-query must be > 0.")

    rerank_rows = load_rerank_rows(args.input_file)
    grouped = group_rows(rerank_rows)
    group_ids = sorted(grouped.keys())

    train_group_ids, eval_group_ids, split_strategy = split_group_ids(
        group_ids,
        grouped_rows=grouped,
        eval_ratio=args.eval_ratio,
        min_eval_queries=args.min_eval_queries,
        seed=args.seed,
    )

    train_rows = build_triplet_rows(
        grouped,
        train_group_ids,
        negatives_per_positive=args.negatives_per_positive,
        max_triplets_per_query=args.max_triplets_per_query,
        prefer_hard_negatives=args.prefer_hard_negatives,
        seed=args.seed,
    )
    eval_rows = build_triplet_rows(
        grouped,
        eval_group_ids,
        negatives_per_positive=args.negatives_per_positive,
        max_triplets_per_query=args.max_triplets_per_query,
        prefer_hard_negatives=args.prefer_hard_negatives,
        seed=args.seed + 1,
    )

    if not train_rows:
        raise RuntimeError("No train triplets generated. Check input label balance.")
    if not eval_rows:
        eval_rows = list(train_rows[: min(len(train_rows), 100)])
        split_strategy = f"{split_strategy}+eval_overlap"

    output_dir: Path = args.output_dir
    _write_jsonl(output_dir / "train_triplets.jsonl", train_rows)
    _write_jsonl(output_dir / "eval_triplets.jsonl", eval_rows)

    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "input_file": str(args.input_file),
        "output_dir": str(output_dir),
        "split_strategy": split_strategy,
        "seed": args.seed,
        "config": {
            "eval_ratio": args.eval_ratio,
            "min_eval_queries": args.min_eval_queries,
            "max_triplets_per_query": args.max_triplets_per_query,
            "negatives_per_positive": args.negatives_per_positive,
            "prefer_hard_negatives": bool(args.prefer_hard_negatives),
        },
        "counts": {
            "n_rerank_rows": len(rerank_rows),
            "n_query_groups": len(group_ids),
            "n_train_query_groups": len(train_group_ids),
            "n_eval_query_groups": len(eval_group_ids),
            "n_train_triplets": len(train_rows),
            "n_eval_triplets": len(eval_rows),
            "train_subdomain_counts": _count_by_subdomain(train_rows),
            "eval_subdomain_counts": _count_by_subdomain(eval_rows),
        },
        "files": {
            "train_triplets": str(output_dir / "train_triplets.jsonl"),
            "eval_triplets": str(output_dir / "eval_triplets.jsonl"),
        },
    }

    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    args = parse_args()
    summary = build_triplet_datasets(args)
    print("Retriever triplet dataset build complete.")
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
