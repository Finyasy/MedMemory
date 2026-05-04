#!/usr/bin/env python3
"""Train a sentence-transformers bi-encoder retriever on triplet data.

Input:
  - data/retriever_triplets/train_triplets.jsonl
  - data/retriever_triplets/eval_triplets.jsonl

Outputs:
  - artifacts/retriever_biencoder/model/
  - artifacts/retriever_biencoder/train_metrics.json
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.optim import AdamW
from transformers import get_linear_schedule_with_warmup


@dataclass(slots=True)
class TripletRow:
    """Single triplet training row."""

    row_id: str
    anchor: str
    positive: str
    negative: str
    subdomain: str
    patient_id: int | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--train-file",
        type=Path,
        default=Path("data/retriever_triplets/train_triplets.jsonl"),
        help="Triplet train JSONL file.",
    )
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=Path("data/retriever_triplets/eval_triplets.jsonl"),
        help="Triplet eval JSONL file.",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="all-MiniLM-L6-v2",
        help="Base sentence-transformers model name/path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/retriever_biencoder"),
        help="Directory for trained model + metrics.",
    )
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--eval-steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--triplet-margin",
        type=float,
        default=0.25,
        help="Triplet loss margin.",
    )
    parser.add_argument(
        "--max-train-rows",
        type=int,
        default=None,
        help="Optional cap on train rows.",
    )
    parser.add_argument(
        "--max-eval-rows",
        type=int,
        default=None,
        help="Optional cap on eval rows.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cpu", "cuda", "mps"],
        help=(
            "Training device. 'auto' prefers CUDA, otherwise CPU. "
            "MPS can be forced but may be unstable for this workload."
        ),
    )
    return parser.parse_args()


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _resolve_device(device_arg: str) -> str:
    if device_arg != "auto":
        if device_arg == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("Requested --device cuda but CUDA is unavailable.")
        if device_arg == "mps":
            mps_available = bool(
                getattr(torch.backends, "mps", None)
                and torch.backends.mps.is_available()
            )
            if not mps_available:
                raise RuntimeError("Requested --device mps but MPS is unavailable.")
        return device_arg

    # Auto mode: prefer CUDA, otherwise CPU (avoid MPS instability for training).
    if torch.cuda.is_available():
        return "cuda"
    if bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()):
        print(
            "MPS is available, but auto mode uses CPU for stability. "
            "Use --device mps to force MPS."
        )
    return "cpu"


def load_triplets(path: Path, limit: int | None = None) -> list[TripletRow]:
    """Load triplet JSONL rows."""
    if not path.exists():
        raise FileNotFoundError(f"Triplet file not found: {path}")

    rows: list[TripletRow] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        anchor = _normalize_text(str(payload.get("anchor") or payload.get("query") or ""))
        positive = _normalize_text(str(payload.get("positive") or ""))
        negative = _normalize_text(str(payload.get("negative") or ""))
        if not anchor or not positive or not negative:
            continue
        rows.append(
            TripletRow(
                row_id=str(payload.get("id") or f"triplet-{idx}"),
                anchor=anchor,
                positive=positive,
                negative=negative,
                subdomain=str(payload.get("subdomain", "unknown")),
                patient_id=(
                    int(payload["patient_id"])
                    if payload.get("patient_id") is not None
                    else None
                ),
            )
        )
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        raise ValueError(f"No valid triplets found in {path}")
    return rows


def _subdomain_counts(rows: list[TripletRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.subdomain] = counts.get(row.subdomain, 0) + 1
    return dict(sorted(counts.items()))


def _evaluate_triplet_accuracy(model: Any, rows: list[TripletRow]) -> float:
    """Compute cosine triplet accuracy: sim(anchor,pos) > sim(anchor,neg)."""
    if not rows:
        return 0.0
    anchors = [row.anchor for row in rows]
    positives = [row.positive for row in rows]
    negatives = [row.negative for row in rows]

    anchor_embeddings = model.encode(
        anchors,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=64,
    )
    positive_embeddings = model.encode(
        positives,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=64,
    )
    negative_embeddings = model.encode(
        negatives,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=64,
    )
    pos_sim = np.sum(anchor_embeddings * positive_embeddings, axis=1)
    neg_sim = np.sum(anchor_embeddings * negative_embeddings, axis=1)
    return float(np.mean(pos_sim > neg_sim))


def train_biencoder(args: argparse.Namespace) -> dict[str, Any]:
    """Train and save a triplet-loss bi-encoder model."""
    try:
        from sentence_transformers import InputExample, SentenceTransformer, losses
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Missing sentence-transformers runtime. "
            "Install dependencies with: cd backend && uv sync"
        ) from exc

    _seed_everything(args.seed)
    device = _resolve_device(args.device)

    train_rows = load_triplets(args.train_file, limit=args.max_train_rows)
    eval_rows = load_triplets(args.eval_file, limit=args.max_eval_rows)

    model = SentenceTransformer(args.model_name, device=device)

    train_examples = [
        InputExample(texts=[row.anchor, row.positive, row.negative]) for row in train_rows
    ]
    train_dataloader = torch.utils.data.DataLoader(
        train_examples,
        shuffle=True,
        batch_size=args.batch_size,
    )
    triplet_loss = losses.TripletLoss(model=model, triplet_margin=args.triplet_margin)

    output_dir: Path = args.output_dir
    model_dir = output_dir / "model"
    output_dir.mkdir(parents=True, exist_ok=True)

    train_dataloader.collate_fn = model.smart_batching_collate
    total_steps = max(1, int(round(len(train_dataloader) * args.epochs)))
    warmup_steps = int(total_steps * args.warmup_ratio)

    optimizer = AdamW(model.parameters(), lr=args.learning_rate)
    scheduler = get_linear_schedule_with_warmup(
        optimizer=optimizer,
        num_warmup_steps=max(warmup_steps, 0),
        num_training_steps=total_steps,
    )

    model.train()
    steps_done = 0
    running_loss = 0.0
    completed_batches = 0
    best_eval_accuracy = float("-inf")
    checkpoint_saved = False
    eval_every = max(args.eval_steps, 0)

    while steps_done < total_steps:
        for batch in train_dataloader:
            if steps_done >= total_steps:
                break
            sentence_features, labels = batch
            loss_value = triplet_loss(sentence_features, labels)
            loss_value.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad(set_to_none=True)

            running_loss += float(loss_value.detach().cpu().item())
            completed_batches += 1
            steps_done += 1

            if eval_every and (steps_done % eval_every == 0):
                model.eval()
                eval_accuracy = _evaluate_triplet_accuracy(model, eval_rows)
                if eval_accuracy > best_eval_accuracy:
                    best_eval_accuracy = eval_accuracy
                    model.save(str(model_dir))
                    checkpoint_saved = True
                model.train()

    if not checkpoint_saved:
        model.save(str(model_dir))
        checkpoint_saved = True

    # Reload best saved model for deterministic post-train metrics
    trained_model = SentenceTransformer(str(model_dir), device=device)
    train_accuracy = _evaluate_triplet_accuracy(trained_model, train_rows)
    eval_accuracy = _evaluate_triplet_accuracy(trained_model, eval_rows)
    avg_train_loss = running_loss / max(completed_batches, 1)

    metrics = {
        "created_at": datetime.now(UTC).isoformat(),
        "run_config": {
            "train_file": str(args.train_file),
            "eval_file": str(args.eval_file),
            "model_name": args.model_name,
            "output_dir": str(args.output_dir),
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "warmup_ratio": args.warmup_ratio,
            "eval_steps": args.eval_steps,
            "seed": args.seed,
            "triplet_margin": args.triplet_margin,
            "device": device,
            "total_steps": total_steps,
            "warmup_steps": warmup_steps,
        },
        "dataset": {
            "n_train_rows": len(train_rows),
            "n_eval_rows": len(eval_rows),
            "train_subdomain_counts": _subdomain_counts(train_rows),
            "eval_subdomain_counts": _subdomain_counts(eval_rows),
        },
        "metrics": {
            "avg_train_loss": avg_train_loss,
            "triplet_accuracy_train": train_accuracy,
            "triplet_accuracy_eval": eval_accuracy,
        },
        "artifacts": {
            "model_dir": str(model_dir),
        },
    }
    (output_dir / "train_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return metrics


def main() -> int:
    args = parse_args()
    metrics = train_biencoder(args)
    print("Retriever bi-encoder training complete.")
    print(json.dumps(metrics["metrics"], indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
