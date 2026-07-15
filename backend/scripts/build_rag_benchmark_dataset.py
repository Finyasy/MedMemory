#!/usr/bin/env python3
"""Build retrieval/reranker/RAG-SFT benchmark datasets from local EHR records.

This script produces:
1) retrieval_eval.jsonl  -> query + gold chunk labels for retrieval evaluation
2) rerank_train.jsonl    -> query/chunk relevance pairs for reranker training
3) rag_sft_train.jsonl   -> grounded instruction pairs for MedGemma SFT

Default output directory:
    backend/data/rag_benchmark
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_db_context
from app.models import Document, Encounter, LabResult, Medication, MemoryChunk

SUPPORTED_SOURCE_TYPES = ("lab_result", "medication", "encounter", "document")
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
WS_RE = re.compile(r"\s+")


@dataclass(slots=True)
class BenchmarkCandidate:
    """Single benchmark query anchored to one structured source record."""

    id: str
    query: str
    patient_id: int
    subdomain: str
    source_type: str
    source_id: int
    source_date: datetime | None
    expected_source_types: list[str]
    expected_date_from: datetime | None
    expected_date_to: datetime | None
    gold_chunks: list[MemoryChunk]
    reference_answer: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/rag_benchmark"),
        help="Directory where JSONL datasets and summary are written.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for patient/example shuffling and negative sampling.",
    )
    parser.add_argument(
        "--eval-patient-ratio",
        type=float,
        default=0.25,
        help="Fraction of patients reserved for retrieval_eval.",
    )
    parser.add_argument(
        "--eval-example-ratio",
        type=float,
        default=0.2,
        help="Fallback example-level eval split when patient split is impossible.",
    )
    parser.add_argument(
        "--min-indexed-chunks-per-patient",
        type=int,
        default=5,
        help="Minimum indexed chunks required to include a patient.",
    )
    parser.add_argument(
        "--max-patients",
        type=int,
        default=0,
        help="Optional cap on patient count (0 = no cap).",
    )
    parser.add_argument(
        "--max-records-per-subdomain-per-patient",
        type=int,
        default=25,
        help="Cap candidate records per subdomain for each patient.",
    )
    parser.add_argument(
        "--min-gold-chunks",
        type=int,
        default=1,
        help="Minimum source-linked chunks required to keep a candidate.",
    )
    parser.add_argument(
        "--max-retrieval-eval-examples",
        type=int,
        default=800,
        help="Cap retrieval_eval rows after splitting (0 = no cap).",
    )
    parser.add_argument(
        "--max-train-queries",
        type=int,
        default=2000,
        help="Cap train candidates used for rerank/SFT generation (0 = no cap).",
    )
    parser.add_argument(
        "--max-positive-chunks-per-query",
        type=int,
        default=2,
        help="Positive chunk rows per query for rerank_train.",
    )
    parser.add_argument(
        "--hard-negatives-per-query",
        type=int,
        default=3,
        help="Lexical-overlap negatives per query for rerank_train.",
    )
    parser.add_argument(
        "--random-negatives-per-query",
        type=int,
        default=1,
        help="Random negatives per query for rerank_train.",
    )
    parser.add_argument(
        "--max-evidence-chunks",
        type=int,
        default=3,
        help="Evidence chunks included in each SFT prompt.",
    )
    return parser.parse_args()


def _normalize_text(value: str) -> str:
    return WS_RE.sub(" ", (value or "").strip())


def _truncate(value: str, max_chars: int) -> str:
    cleaned = _normalize_text(value)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _token_set(value: str) -> set[str]:
    return set(TOKEN_RE.findall((value or "").lower()))


def _to_datetime(value: datetime | date | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    return datetime.combine(value, time.min, tzinfo=UTC)


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _window_from_date(value: datetime | None, days: int) -> tuple[datetime, datetime] | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value - timedelta(days=days), value + timedelta(days=days)


def _serialize_chunk(chunk: MemoryChunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.id,
        "source_type": chunk.source_type,
        "source_id": chunk.source_id,
        "chunk_index": chunk.chunk_index,
        "context_date": _iso_or_none(chunk.context_date),
    }


def _stable_id(prefix: str, patient_id: int, source_type: str, source_id: int) -> str:
    digest = hashlib.sha1(f"{patient_id}:{source_type}:{source_id}".encode()).hexdigest()[
        :16
    ]
    return f"{prefix}_{digest}"


def _lab_reference_answer(lab: LabResult) -> str:
    raw_value: str | None = None
    if lab.value and lab.value.strip():
        raw_value = lab.value.strip()
    elif lab.numeric_value is not None:
        raw_value = f"{lab.numeric_value:g}"

    value_part = raw_value or "value not available"
    unit_part = f" {lab.unit.strip()}" if lab.unit and lab.unit.strip() else ""
    abnormal_part = " It is flagged abnormal." if lab.is_abnormal else ""
    return (
        f"{lab.test_name}: {value_part}{unit_part}.{abnormal_part} "
        f"(source: lab_result#{lab.id})"
    ).strip()


def _medication_reference_answer(med: Medication) -> str:
    status = "active" if med.is_active else "not active"
    details: list[str] = []
    if med.dosage:
        details.append(med.dosage.strip())
    if med.frequency:
        details.append(med.frequency.strip())
    if med.route:
        details.append(f"route {med.route.strip()}")
    detail_text = f" Details: {', '.join(details)}." if details else ""
    return f"{med.name} is {status}.{detail_text} (source: medication#{med.id})"


def _encounter_reference_answer(encounter: Encounter) -> str:
    visit_date = encounter.encounter_date.date().isoformat()
    narrative = (
        encounter.chief_complaint
        or encounter.reason_for_visit
        or encounter.assessment
        or encounter.plan
        or encounter.clinical_notes
        or "Encounter details are available in the record."
    )
    narrative = _truncate(narrative, 220)
    encounter_type = encounter.encounter_type.replace("_", " ")
    return (
        f"{encounter_type.title()} visit on {visit_date}. {narrative} "
        f"(source: encounter#{encounter.id})"
    )


def _document_reference_answer(document: Document, chunks: list[MemoryChunk]) -> str:
    source_label = document.title or document.document_type.replace("_", " ")
    summary = "Key findings are documented in this report."
    if chunks:
        first_chunk = sorted(
            chunks, key=lambda chunk: ((chunk.chunk_index or 0), chunk.id)
        )[0]
        summary = _truncate(first_chunk.content, 220)
    date_hint = document.document_date.date().isoformat() if document.document_date else "unknown date"
    return (
        f"{source_label} ({date_hint}): {summary} "
        f"(source: document#{document.id})"
    )


def _make_sft_prompt(query: str, chunks: list[MemoryChunk], max_evidence_chunks: int) -> str:
    evidence_lines: list[str] = []
    sorted_chunks = sorted(chunks, key=lambda chunk: ((chunk.chunk_index or 0), chunk.id))
    for chunk in sorted_chunks[:max_evidence_chunks]:
        source_id = chunk.source_id if chunk.source_id is not None else "unknown"
        source_ref = f"{chunk.source_type}#{source_id}"
        evidence_lines.append(
            f"[source: {source_ref}] {_truncate(chunk.content, 320)}"
        )

    evidence_block = "\n".join(evidence_lines) if evidence_lines else "[no evidence]"
    return (
        f"Question: {query}\n\n"
        "Answer using only the evidence below. Include source citations in the form "
        "`(source: <type>#<id>)`. If evidence is insufficient, reply exactly: "
        "`I do not know from the available records.`\n\n"
        f"Evidence:\n{evidence_block}"
    )


def _mine_negative_chunks(
    *,
    query: str,
    patient_chunks: list[MemoryChunk],
    gold_chunk_ids: set[int],
    hard_limit: int,
    random_limit: int,
    rng: random.Random,
) -> tuple[list[MemoryChunk], list[MemoryChunk]]:
    non_gold = [chunk for chunk in patient_chunks if chunk.id not in gold_chunk_ids]
    if not non_gold:
        return [], []

    query_tokens = _token_set(query)
    scored: list[tuple[float, MemoryChunk]] = []
    for chunk in non_gold:
        chunk_tokens = _token_set(chunk.content)
        if not query_tokens or not chunk_tokens:
            score = 0.0
        else:
            score = len(query_tokens & chunk_tokens) / max(len(query_tokens), 1)
        scored.append((score, chunk))

    scored.sort(
        key=lambda item: (
            item[0],
            item[1].created_at or datetime.min.replace(tzinfo=UTC),
            item[1].id,
        ),
        reverse=True,
    )

    hard_negatives = [chunk for score, chunk in scored if score > 0][:hard_limit]
    hard_ids = {chunk.id for chunk in hard_negatives}

    remaining = [chunk for chunk in non_gold if chunk.id not in hard_ids]
    random_negatives: list[MemoryChunk] = []
    if remaining and random_limit > 0:
        sample_size = min(random_limit, len(remaining))
        random_negatives = rng.sample(remaining, k=sample_size)

    return hard_negatives, random_negatives


def _to_json_rows_for_retrieval(candidates: list[BenchmarkCandidate]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        row: dict[str, Any] = {
            "id": candidate.id,
            "query": candidate.query,
            "patient_id": candidate.patient_id,
            "subdomain": candidate.subdomain,
            "expected_source_types": candidate.expected_source_types,
            "gold_chunk_ids": [chunk.id for chunk in candidate.gold_chunks],
            "gold_chunks": [_serialize_chunk(chunk) for chunk in candidate.gold_chunks],
            "metadata": {
                "source_type": candidate.source_type,
                "source_id": candidate.source_id,
            },
        }
        if candidate.expected_date_from and candidate.expected_date_to:
            row["expected_time_window"] = {
                "date_from": _iso_or_none(candidate.expected_date_from),
                "date_to": _iso_or_none(candidate.expected_date_to),
            }
        rows.append(row)
    return rows


def _to_json_rows_for_rag_sft(
    candidates: list[BenchmarkCandidate],
    *,
    max_evidence_chunks: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        prompt = _make_sft_prompt(
            query=candidate.query,
            chunks=candidate.gold_chunks,
            max_evidence_chunks=max_evidence_chunks,
        )
        row = {
            "id": candidate.id,
            "prompt": candidate.query,
            "reference_answer": candidate.reference_answer,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": candidate.reference_answer},
            ],
            "metadata": {
                "source": "rag_benchmark",
                "patient_id": candidate.patient_id,
                "subdomain": candidate.subdomain,
                "source_type": candidate.source_type,
                "source_id": candidate.source_id,
                "gold_chunk_ids": [chunk.id for chunk in candidate.gold_chunks],
            },
        }
        rows.append(row)
    return rows


def _to_json_rows_for_reranker(
    candidates: list[BenchmarkCandidate],
    *,
    patient_chunks: dict[int, list[MemoryChunk]],
    max_positive_chunks_per_query: int,
    hard_negatives_per_query: int,
    random_negatives_per_query: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        positives = sorted(
            candidate.gold_chunks,
            key=lambda chunk: ((chunk.chunk_index or 0), chunk.id),
        )[:max_positive_chunks_per_query]
        gold_ids = {chunk.id for chunk in candidate.gold_chunks}
        hard_negatives, random_negatives = _mine_negative_chunks(
            query=candidate.query,
            patient_chunks=patient_chunks.get(candidate.patient_id, []),
            gold_chunk_ids=gold_ids,
            hard_limit=hard_negatives_per_query,
            random_limit=random_negatives_per_query,
            rng=rng,
        )

        if not positives:
            continue
        if not hard_negatives and not random_negatives:
            continue

        group_id = f"rerank_{candidate.id}"
        for chunk in positives:
            rows.append(
                {
                    "id": f"{group_id}_pos_{chunk.id}",
                    "group_id": group_id,
                    "query": candidate.query,
                    "patient_id": candidate.patient_id,
                    "subdomain": candidate.subdomain,
                    "label": 1,
                    "hard_negative": False,
                    "chunk_id": chunk.id,
                    "chunk_text": _truncate(chunk.content, 650),
                    "chunk_source_type": chunk.source_type,
                    "chunk_source_id": chunk.source_id,
                    "chunk_context_date": _iso_or_none(chunk.context_date),
                    "metadata": {
                        "gold_source_type": candidate.source_type,
                        "gold_source_id": candidate.source_id,
                    },
                }
            )

        for chunk in hard_negatives:
            rows.append(
                {
                    "id": f"{group_id}_hard_{chunk.id}",
                    "group_id": group_id,
                    "query": candidate.query,
                    "patient_id": candidate.patient_id,
                    "subdomain": candidate.subdomain,
                    "label": 0,
                    "hard_negative": True,
                    "chunk_id": chunk.id,
                    "chunk_text": _truncate(chunk.content, 650),
                    "chunk_source_type": chunk.source_type,
                    "chunk_source_id": chunk.source_id,
                    "chunk_context_date": _iso_or_none(chunk.context_date),
                    "metadata": {
                        "gold_source_type": candidate.source_type,
                        "gold_source_id": candidate.source_id,
                    },
                }
            )

        for chunk in random_negatives:
            rows.append(
                {
                    "id": f"{group_id}_rnd_{chunk.id}",
                    "group_id": group_id,
                    "query": candidate.query,
                    "patient_id": candidate.patient_id,
                    "subdomain": candidate.subdomain,
                    "label": 0,
                    "hard_negative": False,
                    "chunk_id": chunk.id,
                    "chunk_text": _truncate(chunk.content, 650),
                    "chunk_source_type": chunk.source_type,
                    "chunk_source_id": chunk.source_id,
                    "chunk_context_date": _iso_or_none(chunk.context_date),
                    "metadata": {
                        "gold_source_type": candidate.source_type,
                        "gold_source_id": candidate.source_id,
                    },
                }
            )
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True))
            handle.write("\n")


def _build_lab_candidate(
    lab: LabResult,
    source_chunks: list[MemoryChunk],
    min_gold_chunks: int,
) -> BenchmarkCandidate | None:
    if len(source_chunks) < min_gold_chunks:
        return None
    source_date = _to_datetime(lab.collected_at or lab.resulted_at)
    if source_date is not None:
        query = f"What was my {lab.test_name} result around {source_date.date().isoformat()}?"
        date_window = _window_from_date(source_date, days=7)
    else:
        query = f"What is my latest {lab.test_name} result?"
        date_window = None
    return BenchmarkCandidate(
        id=_stable_id("lab", lab.patient_id, "lab_result", lab.id),
        query=query,
        patient_id=lab.patient_id,
        subdomain="labs",
        source_type="lab_result",
        source_id=lab.id,
        source_date=source_date,
        expected_source_types=["lab_result"],
        expected_date_from=date_window[0] if date_window else None,
        expected_date_to=date_window[1] if date_window else None,
        gold_chunks=source_chunks,
        reference_answer=_lab_reference_answer(lab),
    )


def _build_medication_candidate(
    medication: Medication,
    source_chunks: list[MemoryChunk],
    min_gold_chunks: int,
) -> BenchmarkCandidate | None:
    if len(source_chunks) < min_gold_chunks:
        return None
    source_date = _to_datetime(medication.prescribed_at or medication.start_date)
    query = f"Is {medication.name} currently active, and what is the dosage?"
    date_window = _window_from_date(source_date, days=30) if source_date else None
    return BenchmarkCandidate(
        id=_stable_id("med", medication.patient_id, "medication", medication.id),
        query=query,
        patient_id=medication.patient_id,
        subdomain="medications",
        source_type="medication",
        source_id=medication.id,
        source_date=source_date,
        expected_source_types=["medication"],
        expected_date_from=date_window[0] if date_window else None,
        expected_date_to=date_window[1] if date_window else None,
        gold_chunks=source_chunks,
        reference_answer=_medication_reference_answer(medication),
    )


def _build_encounter_candidate(
    encounter: Encounter,
    source_chunks: list[MemoryChunk],
    min_gold_chunks: int,
) -> BenchmarkCandidate | None:
    if len(source_chunks) < min_gold_chunks:
        return None
    source_date = _to_datetime(encounter.encounter_date)
    date_text = source_date.date().isoformat() if source_date else "most recent"
    encounter_type = encounter.encounter_type.replace("_", " ")
    query = f"What happened during my {encounter_type} visit on {date_text}?"
    date_window = _window_from_date(source_date, days=7) if source_date else None
    return BenchmarkCandidate(
        id=_stable_id("enc", encounter.patient_id, "encounter", encounter.id),
        query=query,
        patient_id=encounter.patient_id,
        subdomain="encounters",
        source_type="encounter",
        source_id=encounter.id,
        source_date=source_date,
        expected_source_types=["encounter"],
        expected_date_from=date_window[0] if date_window else None,
        expected_date_to=date_window[1] if date_window else None,
        gold_chunks=source_chunks,
        reference_answer=_encounter_reference_answer(encounter),
    )


def _build_document_candidate(
    document: Document,
    source_chunks: list[MemoryChunk],
    min_gold_chunks: int,
) -> BenchmarkCandidate | None:
    if len(source_chunks) < min_gold_chunks:
        return None
    source_date = _to_datetime(document.document_date or document.received_date)
    date_hint = source_date.date().isoformat() if source_date else "most recent"
    doc_type = document.document_type.replace("_", " ")
    query = f"What are the key findings in my {doc_type} document from {date_hint}?"
    date_window = _window_from_date(source_date, days=30) if source_date else None
    return BenchmarkCandidate(
        id=_stable_id("doc", document.patient_id, "document", document.id),
        query=query,
        patient_id=document.patient_id,
        subdomain="documents",
        source_type="document",
        source_id=document.id,
        source_date=source_date,
        expected_source_types=["document"],
        expected_date_from=date_window[0] if date_window else None,
        expected_date_to=date_window[1] if date_window else None,
        gold_chunks=source_chunks,
        reference_answer=_document_reference_answer(document, source_chunks),
    )


def _dedupe_candidates(candidates: list[BenchmarkCandidate]) -> list[BenchmarkCandidate]:
    unique: list[BenchmarkCandidate] = []
    seen_ids: set[str] = set()
    seen_keys: set[tuple[int, str, int, str]] = set()
    for candidate in candidates:
        key = (
            candidate.patient_id,
            candidate.source_type,
            candidate.source_id,
            candidate.query.lower(),
        )
        if candidate.id in seen_ids or key in seen_keys:
            continue
        unique.append(candidate)
        seen_ids.add(candidate.id)
        seen_keys.add(key)
    return unique


def _subdomain_counts(candidates: list[BenchmarkCandidate]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for candidate in candidates:
        counts[candidate.subdomain] += 1
    return dict(sorted(counts.items()))


async def build_datasets(args: argparse.Namespace) -> dict[str, Any]:
    rng = random.Random(args.seed)
    output_dir: Path = args.output_dir

    async with get_db_context() as db:
        patient_stmt = (
            select(MemoryChunk.patient_id)
            .where(
                MemoryChunk.is_indexed.is_(True),
                MemoryChunk.source_type.in_(SUPPORTED_SOURCE_TYPES),
                MemoryChunk.source_id.is_not(None),
            )
            .group_by(MemoryChunk.patient_id)
            .having(func.count(MemoryChunk.id) >= args.min_indexed_chunks_per_patient)
        )
        patient_ids = [int(value) for value in (await db.execute(patient_stmt)).scalars().all()]

        if not patient_ids:
            raise RuntimeError(
                "No eligible patients found. Ensure memory_chunks are indexed first."
            )

        rng.shuffle(patient_ids)
        if args.max_patients and args.max_patients > 0:
            patient_ids = patient_ids[: args.max_patients]

        split_strategy = "patient_level"
        if len(patient_ids) >= 2:
            eval_count = max(1, int(round(len(patient_ids) * args.eval_patient_ratio)))
            eval_count = min(eval_count, len(patient_ids) - 1)
            eval_patient_ids = set(patient_ids[:eval_count])
            train_patient_ids = set(patient_ids[eval_count:])
        else:
            eval_patient_ids = set(patient_ids)
            train_patient_ids = set(patient_ids)
            split_strategy = "single_patient_overlap"

        chunk_stmt = select(MemoryChunk).where(
            MemoryChunk.patient_id.in_(patient_ids),
            MemoryChunk.is_indexed.is_(True),
            MemoryChunk.source_type.in_(SUPPORTED_SOURCE_TYPES),
            MemoryChunk.source_id.is_not(None),
        )
        all_chunks = list((await db.execute(chunk_stmt)).scalars().all())

        chunks_by_source: dict[tuple[int, str, int], list[MemoryChunk]] = defaultdict(list)
        chunks_by_patient: dict[int, list[MemoryChunk]] = defaultdict(list)
        for chunk in all_chunks:
            if chunk.source_id is None:
                continue
            source_key = (chunk.patient_id, chunk.source_type, int(chunk.source_id))
            chunks_by_source[source_key].append(chunk)
            chunks_by_patient[chunk.patient_id].append(chunk)

        for source_list in chunks_by_source.values():
            source_list.sort(key=lambda chunk: ((chunk.chunk_index or 0), chunk.id))

        cap = args.max_records_per_subdomain_per_patient
        usage_counter: dict[tuple[int, str], int] = defaultdict(int)
        candidates: list[BenchmarkCandidate] = []

        lab_rows = list(
            (
                await db.execute(
                    select(LabResult).where(LabResult.patient_id.in_(patient_ids))
                )
            )
            .scalars()
            .all()
        )
        for lab in lab_rows:
            usage_key = (lab.patient_id, "labs")
            if usage_counter[usage_key] >= cap:
                continue
            candidate = _build_lab_candidate(
                lab=lab,
                source_chunks=chunks_by_source.get(
                    (lab.patient_id, "lab_result", lab.id), []
                ),
                min_gold_chunks=args.min_gold_chunks,
            )
            if candidate is None:
                continue
            candidates.append(candidate)
            usage_counter[usage_key] += 1

        medication_rows = list(
            (
                await db.execute(
                    select(Medication).where(Medication.patient_id.in_(patient_ids))
                )
            )
            .scalars()
            .all()
        )
        for medication in medication_rows:
            usage_key = (medication.patient_id, "medications")
            if usage_counter[usage_key] >= cap:
                continue
            candidate = _build_medication_candidate(
                medication=medication,
                source_chunks=chunks_by_source.get(
                    (medication.patient_id, "medication", medication.id), []
                ),
                min_gold_chunks=args.min_gold_chunks,
            )
            if candidate is None:
                continue
            candidates.append(candidate)
            usage_counter[usage_key] += 1

        encounter_rows = list(
            (
                await db.execute(
                    select(Encounter).where(Encounter.patient_id.in_(patient_ids))
                )
            )
            .scalars()
            .all()
        )
        for encounter in encounter_rows:
            usage_key = (encounter.patient_id, "encounters")
            if usage_counter[usage_key] >= cap:
                continue
            candidate = _build_encounter_candidate(
                encounter=encounter,
                source_chunks=chunks_by_source.get(
                    (encounter.patient_id, "encounter", encounter.id), []
                ),
                min_gold_chunks=args.min_gold_chunks,
            )
            if candidate is None:
                continue
            candidates.append(candidate)
            usage_counter[usage_key] += 1

        document_rows = list(
            (
                await db.execute(
                    select(Document).where(
                        Document.patient_id.in_(patient_ids),
                        Document.is_processed.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        for document in document_rows:
            usage_key = (document.patient_id, "documents")
            if usage_counter[usage_key] >= cap:
                continue
            candidate = _build_document_candidate(
                document=document,
                source_chunks=chunks_by_source.get(
                    (document.patient_id, "document", document.id), []
                ),
                min_gold_chunks=args.min_gold_chunks,
            )
            if candidate is None:
                continue
            candidates.append(candidate)
            usage_counter[usage_key] += 1

    candidates = _dedupe_candidates(candidates)
    if not candidates:
        raise RuntimeError("No benchmark candidates were generated from current data.")

    rng.shuffle(candidates)

    if split_strategy == "patient_level":
        train_candidates = [
            candidate for candidate in candidates if candidate.patient_id in train_patient_ids
        ]
        eval_candidates = [
            candidate for candidate in candidates if candidate.patient_id in eval_patient_ids
        ]
        if not train_candidates or not eval_candidates:
            split_strategy = "example_level_fallback"

    if split_strategy != "patient_level":
        shuffled = list(candidates)
        rng.shuffle(shuffled)
        if len(shuffled) == 1:
            eval_candidates = shuffled[:]
            train_candidates = shuffled[:]
            split_strategy = "example_overlap"
        else:
            eval_count = max(1, int(round(len(shuffled) * args.eval_example_ratio)))
            eval_count = min(eval_count, len(shuffled) - 1)
            eval_candidates = shuffled[:eval_count]
            train_candidates = shuffled[eval_count:]

    if args.max_retrieval_eval_examples and args.max_retrieval_eval_examples > 0:
        eval_candidates = eval_candidates[: args.max_retrieval_eval_examples]
    if args.max_train_queries and args.max_train_queries > 0:
        train_candidates = train_candidates[: args.max_train_queries]

    if not eval_candidates and candidates:
        if args.max_retrieval_eval_examples and args.max_retrieval_eval_examples > 0:
            fallback_n = min(args.max_retrieval_eval_examples, len(candidates))
        else:
            fallback_n = min(1, len(candidates))
        eval_candidates = candidates[:fallback_n]

    retrieval_rows = _to_json_rows_for_retrieval(eval_candidates)
    rerank_rows = _to_json_rows_for_reranker(
        train_candidates,
        patient_chunks=chunks_by_patient,
        max_positive_chunks_per_query=args.max_positive_chunks_per_query,
        hard_negatives_per_query=args.hard_negatives_per_query,
        random_negatives_per_query=args.random_negatives_per_query,
        rng=rng,
    )
    rag_sft_rows = _to_json_rows_for_rag_sft(
        train_candidates,
        max_evidence_chunks=args.max_evidence_chunks,
    )

    _write_jsonl(output_dir / "retrieval_eval.jsonl", retrieval_rows)
    _write_jsonl(output_dir / "rerank_train.jsonl", rerank_rows)
    _write_jsonl(output_dir / "rag_sft_train.jsonl", rag_sft_rows)

    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "output_dir": str(output_dir),
        "split_strategy": split_strategy,
        "seed": args.seed,
        "config": {
            "eval_patient_ratio": args.eval_patient_ratio,
            "eval_example_ratio": args.eval_example_ratio,
            "min_indexed_chunks_per_patient": args.min_indexed_chunks_per_patient,
            "max_patients": args.max_patients,
            "max_records_per_subdomain_per_patient": args.max_records_per_subdomain_per_patient,
            "min_gold_chunks": args.min_gold_chunks,
            "max_retrieval_eval_examples": args.max_retrieval_eval_examples,
            "max_train_queries": args.max_train_queries,
            "max_positive_chunks_per_query": args.max_positive_chunks_per_query,
            "hard_negatives_per_query": args.hard_negatives_per_query,
            "random_negatives_per_query": args.random_negatives_per_query,
            "max_evidence_chunks": args.max_evidence_chunks,
        },
        "counts": {
            "n_total_candidates": len(candidates),
            "n_train_candidates": len(train_candidates),
            "n_eval_candidates": len(eval_candidates),
            "retrieval_eval_rows": len(retrieval_rows),
            "rerank_train_rows": len(rerank_rows),
            "rag_sft_train_rows": len(rag_sft_rows),
            "train_subdomain_counts": _subdomain_counts(train_candidates),
            "eval_subdomain_counts": _subdomain_counts(eval_candidates),
        },
        "files": {
            "retrieval_eval": str(output_dir / "retrieval_eval.jsonl"),
            "rerank_train": str(output_dir / "rerank_train.jsonl"),
            "rag_sft_train": str(output_dir / "rag_sft_train.jsonl"),
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return summary


async def main_async() -> int:
    args = parse_args()
    summary = await build_datasets(args)
    print("RAG benchmark dataset build complete.")
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
