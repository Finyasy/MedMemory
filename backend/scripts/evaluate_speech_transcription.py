"""Evaluate local MedASR transcription quality on one or more audio clips.

Usage:
    uv run python scripts/evaluate_speech_transcription.py \
      --audio /tmp/patient-question.wav \
      --audio /tmp/clinician-question.m4a \
      --output-dir artifacts/speech_eval/current \
      --compare-plain-ctc

    uv run python scripts/evaluate_speech_transcription.py \
      --manifest data/speech_eval/manifest.jsonl \
      --output-dir artifacts/speech_eval/current
"""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.speech.transcribe import SpeechTranscriptionService


@dataclass(frozen=True)
class EvalExample:
    example_id: str
    audio_path: Path
    reference: str | None = None
    metadata: dict[str, Any] | None = None


class LocalUploadFile:
    def __init__(self, audio_path: Path) -> None:
        self._audio_path = audio_path
        self.filename = audio_path.name
        self.content_type = mimetypes.guess_type(audio_path.name)[0] or "audio/wav"

    async def read(self) -> bytes:
        return self._audio_path.read_bytes()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audio",
        action="append",
        default=[],
        help="Audio file to transcribe. Repeat for multiple clips.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Optional JSONL manifest with {id,audio_path,reference}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/speech_eval/current"),
        help="Directory where JSON and Markdown reports are written.",
    )
    parser.add_argument(
        "--compare-plain-ctc",
        action="store_true",
        help="Evaluate both LM-backed decode and plain CTC decode.",
    )
    return parser.parse_args()


def load_examples(args: argparse.Namespace) -> list[EvalExample]:
    examples: list[EvalExample] = []
    for index, raw_audio_path in enumerate(args.audio, start=1):
        audio_path = Path(raw_audio_path).expanduser().resolve()
        examples.append(
            EvalExample(
                example_id=f"audio-{index}",
                audio_path=audio_path,
            )
        )
    if args.manifest:
        if not args.manifest.exists():
            raise FileNotFoundError(f"Manifest not found: {args.manifest}")
        manifest_root = args.manifest.parent.resolve()
        with args.manifest.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                payload = json.loads(line)
                raw_audio_path = Path(payload["audio_path"]).expanduser()
                audio_path = (
                    raw_audio_path.resolve()
                    if raw_audio_path.is_absolute()
                    else (manifest_root / raw_audio_path).resolve()
                )
                examples.append(
                    EvalExample(
                        example_id=str(payload.get("id") or f"manifest-{index}"),
                        audio_path=audio_path,
                        reference=payload.get("reference"),
                        metadata={
                            key: value
                            for key, value in payload.items()
                            if key not in {"id", "audio_path", "reference"}
                        }
                        or None,
                    )
                )
    if not examples:
        raise ValueError("Provide at least one --audio clip or a --manifest file.")
    missing_paths = [str(example.audio_path) for example in examples if not example.audio_path.exists()]
    if missing_paths:
        raise FileNotFoundError(
            "Audio files not found:\n" + "\n".join(f"- {path}" for path in missing_paths)
        )
    return examples


@contextmanager
def override_settings(**overrides: Any):
    originals = {key: getattr(settings, key) for key in overrides}
    for key, value in overrides.items():
        setattr(settings, key, value)
    try:
        yield
    finally:
        for key, value in originals.items():
            setattr(settings, key, value)


async def build_service(*, use_lm_decoder: bool) -> SpeechTranscriptionService:
    with override_settings(speech_transcription_use_lm_decoder=use_lm_decoder):
        service = SpeechTranscriptionService()
        await service._get_pipeline()
        return service


def normalize_words(text: str) -> list[str]:
    return [token for token in text.lower().split() if token]


def compute_word_error_rate(reference: str, hypothesis: str) -> float:
    reference_words = normalize_words(reference)
    hypothesis_words = normalize_words(hypothesis)
    if not reference_words:
        return 0.0 if not hypothesis_words else 1.0

    distances = list(range(len(hypothesis_words) + 1))
    for row_index, reference_word in enumerate(reference_words, start=1):
        previous_diagonal = distances[0]
        distances[0] = row_index
        for column_index, hypothesis_word in enumerate(hypothesis_words, start=1):
            current = distances[column_index]
            if reference_word == hypothesis_word:
                distances[column_index] = previous_diagonal
            else:
                distances[column_index] = min(
                    previous_diagonal + 1,
                    distances[column_index] + 1,
                    distances[column_index - 1] + 1,
                )
            previous_diagonal = current
    return distances[-1] / len(reference_words)


async def run_mode(
    *,
    service: SpeechTranscriptionService,
    examples: Iterable[EvalExample],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for example in examples:
        result = await service.transcribe(
            audio=LocalUploadFile(example.audio_path),
            language="en",
            patient_id=None,
            clinician_mode=False,
        )
        row = {
            "id": example.example_id,
            "audio_path": str(example.audio_path),
            "reference": example.reference,
            "transcript": result.transcript,
            "confidence": result.transcript_confidence,
            "duration_ms": result.duration_ms,
            "decoder_mode": service._decoder_mode,
            "model_name": result.model_name,
        }
        if example.reference:
            row["word_error_rate"] = compute_word_error_rate(
                example.reference,
                result.transcript,
            )
        if example.metadata:
            row["metadata"] = example.metadata
        rows.append(row)
    return rows


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    references = [row["word_error_rate"] for row in rows if row.get("word_error_rate") is not None]
    confidences = [row["confidence"] for row in rows if row.get("confidence") is not None]
    summary: dict[str, Any] = {
        "example_count": len(rows),
        "average_word_error_rate": round(sum(references) / len(references), 4)
        if references
        else None,
        "average_confidence": round(sum(confidences) / len(confidences), 4)
        if confidences
        else None,
        "by_role": {},
        "by_environment": {},
    }
    for field, bucket_name in (("role", "by_role"), ("environment", "by_environment")):
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            value = (row.get("metadata") or {}).get(field)
            if not value:
                continue
            buckets.setdefault(str(value), []).append(row)
        summary[bucket_name] = {
            key: {
                "example_count": len(value_rows),
                "average_word_error_rate": round(
                    sum(
                        item["word_error_rate"]
                        for item in value_rows
                        if item.get("word_error_rate") is not None
                    )
                    / len([item for item in value_rows if item.get("word_error_rate") is not None]),
                    4,
                )
                if any(item.get("word_error_rate") is not None for item in value_rows)
                else None,
                "average_confidence": round(
                    sum(
                        item["confidence"]
                        for item in value_rows
                        if item.get("confidence") is not None
                    )
                    / len([item for item in value_rows if item.get("confidence") is not None]),
                    4,
                )
                if any(item.get("confidence") is not None for item in value_rows)
                else None,
            }
            for key, value_rows in buckets.items()
        }
    return summary


def write_outputs(
    *,
    output_dir: Path,
    summary: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report_lines = [
        "# Speech Transcription Evaluation",
        "",
        f"- `model_path`: {summary['model_path']}",
        f"- `compare_plain_ctc`: {summary['compare_plain_ctc']}",
        "",
    ]
    for mode, rows in summary["runs"].items():
        report_lines.extend([f"## `{mode}`", ""])
        mode_summary = summary["run_summaries"][mode]
        report_lines.append(f"- `example_count`: {mode_summary['example_count']}")
        report_lines.append(
            f"- `average_word_error_rate`: {mode_summary['average_word_error_rate']}"
        )
        report_lines.append(f"- `average_confidence`: {mode_summary['average_confidence']}")
        if mode_summary["by_role"]:
            report_lines.append(f"- `by_role`: {json.dumps(mode_summary['by_role'], ensure_ascii=False)}")
        if mode_summary["by_environment"]:
            report_lines.append(
                f"- `by_environment`: {json.dumps(mode_summary['by_environment'], ensure_ascii=False)}"
            )
        report_lines.append("")
        for row in rows:
            report_lines.append(f"### `{row['id']}`")
            report_lines.append(f"- `audio_path`: {row['audio_path']}")
            report_lines.append(f"- `transcript`: {row['transcript']}")
            report_lines.append(f"- `confidence`: {row['confidence']}")
            if row.get("reference"):
                report_lines.append(f"- `reference`: {row['reference']}")
                report_lines.append(f"- `word_error_rate`: {row.get('word_error_rate')}")
            if row.get("metadata"):
                report_lines.append(
                    f"- `metadata`: {json.dumps(row['metadata'], ensure_ascii=False)}"
                )
            report_lines.append("")
    (output_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")


async def main() -> None:
    args = parse_args()
    examples = load_examples(args)

    runs: dict[str, list[dict[str, Any]]] = {}
    lm_service = await build_service(use_lm_decoder=True)
    runs["ctc_with_lm"] = await run_mode(service=lm_service, examples=examples)

    if args.compare_plain_ctc:
        ctc_service = await build_service(use_lm_decoder=False)
        runs["ctc"] = await run_mode(
            service=ctc_service,
            examples=examples,
        )

    summary = {
        "model_path": str(lm_service.model_path) if lm_service.model_path else lm_service.model_name,
        "compare_plain_ctc": args.compare_plain_ctc,
        "examples": [
            {
                "id": example.example_id,
                "audio_path": str(example.audio_path),
                "reference": example.reference,
            }
            for example in examples
        ],
        "runs": runs,
        "run_summaries": {
            mode: summarize_rows(rows)
            for mode, rows in runs.items()
        },
    }
    write_outputs(output_dir=args.output_dir, summary=summary)
    print(f"Wrote speech evaluation summary to {args.output_dir / 'summary.json'}")


if __name__ == "__main__":
    asyncio.run(main())
