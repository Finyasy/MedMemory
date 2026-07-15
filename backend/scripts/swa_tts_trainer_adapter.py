#!/usr/bin/env python3
"""Prepare a backend-specific Swahili TTS trainer workspace.

This adapter turns the generic MedMemory trainer contract into a concrete
backend workspace shape. The current backend target is `coqui_vits`.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any


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
    parser.add_argument(
        "--backend",
        choices=("coqui_vits",),
        default="coqui_vits",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Reserved for when the actual backend trainer runtime is installed.",
    )
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_metadata(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="|")
        return list(reader)


def _write_coqui_filelist(rows: list[dict[str, str]], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="|")
        for row in rows:
            writer.writerow([row["audio_file"], row["text"], row["speaker_id"]])
    return len(rows)


def _prepare_coqui_backend(args: argparse.Namespace) -> dict[str, Any]:
    resolved_config = _read_json(args.resolved_config)
    dataset_summary = _read_json(args.dataset_summary)
    backend_root = args.output_json.parent / "coqui_vits"
    backend_root.mkdir(parents=True, exist_ok=True)

    train_rows = _read_metadata(args.train_metadata)
    validation_rows = _read_metadata(args.validation_metadata)
    test_rows = _read_metadata(args.test_metadata)

    train_filelist = backend_root / "train_filelist.txt"
    validation_filelist = backend_root / "validation_filelist.txt"
    test_filelist = backend_root / "test_filelist.txt"
    _write_coqui_filelist(train_rows, train_filelist)
    _write_coqui_filelist(validation_rows, validation_filelist)
    _write_coqui_filelist(test_rows, test_filelist)

    trainer_plan = {
        "status": "prepared_backend",
        "backend": "coqui_vits",
        "execute_requested": args.execute,
        "trainer_available": importlib.util.find_spec("TTS") is not None,
        "resolved_config": str(args.resolved_config.resolve()),
        "dataset_summary": str(args.dataset_summary.resolve()),
        "audio_base_dir": str(args.audio_base_dir.resolve()),
        "base_model_path": str(args.base_model_path.resolve()),
        "checkpoint_dir": str(args.checkpoint_dir.resolve()),
        "reports_dir": str(args.reports_dir.resolve()),
        "backend_workspace": str(backend_root.resolve()),
        "filelists": {
            "train": str(train_filelist.resolve()),
            "validation": str(validation_filelist.resolve()),
            "test": str(test_filelist.resolve()),
        },
        "row_counts": {
            "train": len(train_rows),
            "validation": len(validation_rows),
            "test": len(test_rows),
        },
        "dataset_summary_counts": {
            split_name: summary["row_count"]
            for split_name, summary in dataset_summary.items()
        },
        "dataset_sha": resolved_config["dataset"].get("dataset_sha"),
        "sample_rate_hz": resolved_config["training"].get("sample_rate_hz"),
        "notes": [
            "This adapter prepares a Coqui-style backend workspace from the MedMemory trainer contract.",
            "Actual training execution remains gated until the target trainer runtime is installed and mapped to the base checkpoint strategy.",
        ],
    }
    backend_plan_path = backend_root / "backend_plan.json"
    backend_plan_path.write_text(
        json.dumps(trainer_plan, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    trainer_plan["backend_plan"] = str(backend_plan_path.resolve())
    return trainer_plan


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

    if args.backend != "coqui_vits":
        raise ValueError(f"Unsupported backend: {args.backend}")

    payload = _prepare_coqui_backend(args)
    args.output_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
