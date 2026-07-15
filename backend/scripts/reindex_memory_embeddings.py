#!/usr/bin/env python3
"""Reindex memory_chunks embeddings with a selected sentence-transformers model.

This updates existing memory chunk vectors in place so retrieval uses the new
bi-encoder embedding space.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import and_, func, select

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.database import get_db_context
from app.models import MemoryChunk
from app.services.embeddings.embedding import EmbeddingService, MissingMLDependencyError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-name",
        type=str,
        required=True,
        help=(
            "Embedding model name/path used for reindexing "
            "(for example: artifacts/retriever_biencoder/model)"
        ),
    )
    parser.add_argument(
        "--source-types",
        type=str,
        default="",
        help="Optional comma-separated source_type filter (e.g. document,lab_result).",
    )
    parser.add_argument(
        "--patient-ids",
        type=str,
        default="",
        help="Optional comma-separated patient IDs filter.",
    )
    parser.add_argument(
        "--where-embedding-model",
        type=str,
        default="",
        help="Optional filter: only reindex rows with this existing embedding_model.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Batch size for embedding generation and DB updates.",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=0,
        help="Optional cap on number of chunks reindexed (0 = no cap).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show counts and validation without writing DB updates.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("artifacts/retriever_reindex/last_run.json"),
        help="Summary JSON output path.",
    )
    return parser.parse_args()


def _parse_csv_ints(raw: str) -> list[int]:
    values: list[int] = []
    if not raw.strip():
        return values
    for token in raw.split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        values.append(int(cleaned))
    return values


def _parse_csv_strings(raw: str) -> list[str]:
    values: list[str] = []
    if not raw.strip():
        return values
    for token in raw.split(","):
        cleaned = token.strip()
        if cleaned:
            values.append(cleaned)
    return values


def _base_filters(args: argparse.Namespace) -> list[Any]:
    filters: list[Any] = [MemoryChunk.content.is_not(None)]

    source_types = _parse_csv_strings(args.source_types)
    if source_types:
        filters.append(MemoryChunk.source_type.in_(source_types))

    patient_ids = _parse_csv_ints(args.patient_ids)
    if patient_ids:
        filters.append(MemoryChunk.patient_id.in_(patient_ids))

    if args.where_embedding_model.strip():
        filters.append(MemoryChunk.embedding_model == args.where_embedding_model.strip())

    return filters


async def run_reindex(args: argparse.Namespace) -> dict[str, Any]:
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be > 0")
    if args.max_chunks < 0:
        raise ValueError("--max-chunks must be >= 0")

    try:
        embedding_service = EmbeddingService(model_name=args.model_name)
        model_dimension = int(embedding_service.dimension)
    except MissingMLDependencyError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to initialize embedding model '{args.model_name}': {exc}") from exc

    expected_dimension = int(settings.embedding_dimension)
    if model_dimension != expected_dimension:
        raise RuntimeError(
            "Embedding dimension mismatch: "
            f"model '{args.model_name}' -> {model_dimension}, "
            f"configured EMBEDDING_DIMENSION -> {expected_dimension}. "
            "Update config/schema before reindexing."
        )

    filters = _base_filters(args)
    started_at = datetime.now(UTC)
    updated_chunks = 0
    scanned_chunks = 0
    skipped_empty = 0
    errors = 0
    last_id = 0

    async with get_db_context() as db:
        count_stmt = (
            select(func.count(MemoryChunk.id))
            .where(and_(*filters))
        )
        total_available = int((await db.execute(count_stmt)).scalar_one())

        if args.max_chunks and args.max_chunks > 0:
            target_total = min(total_available, args.max_chunks)
        else:
            target_total = total_available

        if args.dry_run:
            ended_at = datetime.now(UTC)
            return {
                "created_at": ended_at.isoformat(),
                "mode": "dry_run",
                "model_name": args.model_name,
                "model_dimension": model_dimension,
                "target_chunks": target_total,
                "total_available": total_available,
                "filters": {
                    "source_types": _parse_csv_strings(args.source_types),
                    "patient_ids": _parse_csv_ints(args.patient_ids),
                    "where_embedding_model": args.where_embedding_model.strip() or None,
                },
                "duration_seconds": (ended_at - started_at).total_seconds(),
            }

        while updated_chunks < target_total:
            remaining = target_total - updated_chunks
            limit = min(args.batch_size, remaining)
            batch_filters = list(filters)
            batch_filters.append(MemoryChunk.id > last_id)
            stmt = (
                select(MemoryChunk)
                .where(and_(*batch_filters))
                .order_by(MemoryChunk.id.asc())
                .limit(limit)
            )
            rows = list((await db.execute(stmt)).scalars().all())
            if not rows:
                break

            scanned_chunks += len(rows)
            last_id = max(chunk.id for chunk in rows)

            valid_chunks: list[MemoryChunk] = []
            texts: list[str] = []
            for chunk in rows:
                content = (chunk.content or "").strip()
                if not content:
                    skipped_empty += 1
                    continue
                valid_chunks.append(chunk)
                texts.append(content)

            if not valid_chunks:
                continue

            try:
                embeddings = await embedding_service.embed_texts_async(texts)
            except Exception:
                errors += len(valid_chunks)
                continue

            if len(embeddings) != len(valid_chunks):
                raise RuntimeError(
                    "Embedding count mismatch during reindex: "
                    f"expected {len(valid_chunks)} got {len(embeddings)}"
                )

            now = datetime.now(UTC)
            for chunk, embedding in zip(valid_chunks, embeddings, strict=True):
                chunk.embedding = embedding
                chunk.embedding_model = args.model_name
                chunk.is_indexed = True
                chunk.indexed_at = now
                updated_chunks += 1
                if updated_chunks >= target_total:
                    break

            await db.flush()
            await db.commit()

    ended_at = datetime.now(UTC)
    return {
        "created_at": ended_at.isoformat(),
        "mode": "apply",
        "model_name": args.model_name,
        "model_dimension": model_dimension,
        "expected_dimension": expected_dimension,
        "target_chunks": target_total,
        "updated_chunks": updated_chunks,
        "scanned_chunks": scanned_chunks,
        "skipped_empty_chunks": skipped_empty,
        "embedding_errors": errors,
        "filters": {
            "source_types": _parse_csv_strings(args.source_types),
            "patient_ids": _parse_csv_ints(args.patient_ids),
            "where_embedding_model": args.where_embedding_model.strip() or None,
        },
        "duration_seconds": (ended_at - started_at).total_seconds(),
    }


async def main_async() -> int:
    args = parse_args()
    summary = await run_reindex(args)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print("Memory embedding reindex complete.")
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
