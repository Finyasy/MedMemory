#!/usr/bin/env python3
"""Validate the external Swahili TTS trainer command contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolved-config", type=Path, required=True)
    parser.add_argument("--dataset-summary", type=Path, required=True)
    parser.add_argument("--audio-base-dir", type=Path, required=True)
    parser.add_argument("--train-metadata", type=Path, required=True)
    parser.add_argument("--validation-metadata", type=Path, required=True)
    parser.add_argument("--test-metadata", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--base-model-path", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for path in (
        args.resolved_config,
        args.dataset_summary,
        args.audio_base_dir,
        args.train_metadata,
        args.validation_metadata,
        args.test_metadata,
        args.base_model_path,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    args.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "status": "external_contract_verified",
        "resolved_config": str(args.resolved_config.resolve()),
        "dataset_summary": str(args.dataset_summary.resolve()),
        "audio_base_dir": str(args.audio_base_dir.resolve()),
        "train_metadata": str(args.train_metadata.resolve()),
        "validation_metadata": str(args.validation_metadata.resolve()),
        "test_metadata": str(args.test_metadata.resolve()),
        "checkpoint_dir": str(args.checkpoint_dir.resolve()),
        "reports_dir": str(args.reports_dir.resolve()),
        "base_model_path": str(args.base_model_path.resolve()),
    }
    args.output_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
