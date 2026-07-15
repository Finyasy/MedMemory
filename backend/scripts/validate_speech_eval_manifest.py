"""Validate and summarize a human-audio MedASR evaluation manifest.

Usage:
    uv run python scripts/validate_speech_eval_manifest.py \
      --manifest data/speech_eval/human_en_v1/manifest.jsonl \
      --output-json artifacts/speech_eval/human_en_v1/manifest_summary.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from scripts.evaluate_speech_transcription import load_examples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="JSONL manifest with at least {id, audio_path, reference}.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional path to write the manifest summary JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    examples = load_examples(
        argparse.Namespace(
            audio=[],
            manifest=args.manifest,
        )
    )
    role_counts = Counter(str((example.metadata or {}).get("role", "unknown")) for example in examples)
    environment_counts = Counter(
        str((example.metadata or {}).get("environment", "unknown")) for example in examples
    )
    speaker_counts = Counter(
        str((example.metadata or {}).get("speaker_id", "unknown")) for example in examples
    )
    summary = {
        "manifest_path": str(args.manifest.resolve()),
        "example_count": len(examples),
        "roles": dict(role_counts),
        "environments": dict(environment_counts),
        "speakers": dict(speaker_counts),
        "missing_reference_ids": [
            example.example_id for example in examples if not example.reference
        ],
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
