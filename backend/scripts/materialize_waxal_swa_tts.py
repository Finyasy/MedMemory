"""Download and normalize the `google/WaxalNLP` `swa_tts` subset locally.

Usage:
    uv run --group finetune python scripts/materialize_waxal_swa_tts.py \
      --output-dir data/waxal_swa_tts
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, snapshot_download


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-id",
        default="google/WaxalNLP",
        help="Hugging Face dataset identifier.",
    )
    parser.add_argument(
        "--config-name",
        default="swa_tts",
        help="Logical subset name to materialize. `swa_tts` maps to WAXAL `data/TTS/swa`.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/waxal_swa_tts"),
        help="Local directory for cache, manifests, and summaries.",
    )
    parser.add_argument(
        "--max-rows-per-split",
        type=int,
        default=None,
        help="Optional cap for local smoke runs.",
    )
    return parser.parse_args()


def _require_datasets():
    try:
        from datasets import Audio, load_dataset
    except ImportError as exc:  # pragma: no cover - exercised operationally
        raise SystemExit(
            "The `datasets` package is required. Run with `uv run --group finetune`."
        ) from exc
    return Audio, load_dataset


def _resolve_repo_subdir(config_name: str) -> str:
    mapping = {
        "swa_tts": "data/TTS/swa",
    }
    return mapping.get(config_name, config_name)


def _discover_audio_column(features: Any) -> str:
    for name, feature in features.items():
        if feature.__class__.__name__ == "Audio":
            return name
    for candidate in ("audio", "speech"):
        if candidate in features:
            return candidate
    raise ValueError(f"Could not determine audio column from features: {list(features.keys())}")


def _discover_text_column(features: Any) -> str:
    for candidate in (
        "text",
        "sentence",
        "transcript",
        "normalized_text",
        "utterance",
    ):
        if candidate in features:
            return candidate
    raise ValueError(f"Could not determine text column from features: {list(features.keys())}")


def _normalize_audio_path(
    *,
    audio_value: Any,
    output_dir: Path,
    export_dir: Path,
    record_id: str,
) -> str:
    if isinstance(audio_value, dict):
        existing_path = audio_value.get("path")
        if existing_path and Path(existing_path).exists():
            return os.path.relpath(Path(existing_path), output_dir)
        audio_bytes = audio_value.get("bytes")
        if audio_bytes:
            export_dir.mkdir(parents=True, exist_ok=True)
            if audio_bytes.startswith(b"RIFF"):
                extension = ".wav"
            elif audio_bytes.startswith(b"ID3") or audio_bytes[:2] == b"\xff\xfb":
                extension = ".mp3"
            elif audio_bytes.startswith(b"fLaC"):
                extension = ".flac"
            else:
                extension = ".bin"
            export_path = export_dir / f"{record_id}{extension}"
            export_path.write_bytes(audio_bytes)
            return os.path.relpath(export_path, output_dir)
    raise ValueError(f"Audio payload for {record_id} does not expose a local path or bytes.")


def _normalize_row(
    *,
    row: dict[str, Any],
    index: int,
    split: str,
    audio_column: str,
    text_column: str,
    output_dir: Path,
    export_dir: Path,
) -> dict[str, Any]:
    record_id = str(
        row.get("id")
        or row.get("segment_id")
        or row.get("utterance_id")
        or f"{split}-{index:06d}"
    )
    normalized = {
        "id": record_id,
        "split": split,
        "audio_path": _normalize_audio_path(
            audio_value=row[audio_column],
            output_dir=output_dir,
            export_dir=export_dir,
            record_id=record_id,
        ),
        "text": str(row[text_column]).strip(),
        "language": row.get("language") or "sw",
        "source_dataset": "google/WaxalNLP",
        "source_config": "swa_tts",
    }
    for key in ("speaker_id", "gender", "speaker_gender", "locale", "region", "duration"):
        if row.get(key) is not None:
            normalized[key] = row[key]
    return normalized


def main() -> None:
    args = parse_args()
    Audio, load_dataset = _require_datasets()

    output_dir = args.output_dir.expanduser().resolve()
    cache_dir = output_dir / "hf_cache"
    manifests_dir = output_dir / "manifests"
    exported_audio_dir = output_dir / "exported_audio"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    repo_subdir = _resolve_repo_subdir(args.config_name)
    snapshot_download(
        repo_id=args.dataset_id,
        repo_type="dataset",
        allow_patterns=[f"{repo_subdir}/*", "README.md", ".gitattributes"],
        local_dir=str(cache_dir),
    )

    parquet_files = sorted((cache_dir / repo_subdir).glob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(
            f"No parquet files found under {cache_dir / repo_subdir} for {args.config_name}"
        )

    data_files: dict[str, list[str]] = {}
    for path in parquet_files:
        name = path.name.lower()
        if "validation" in name:
            split = "validation"
        elif "test" in name:
            split = "test"
        else:
            split = "train"
        data_files.setdefault(split, []).append(str(path))

    dataset = load_dataset(
        "parquet",
        data_files=data_files,
        cache_dir=str(cache_dir / "datasets_cache"),
    )
    splits = list(dataset.keys())
    reference_split = dataset[splits[0]]
    audio_column = _discover_audio_column(reference_split.features)
    text_column = _discover_text_column(reference_split.features)

    api = HfApi()
    dataset_info = api.dataset_info(args.dataset_id)
    summary: dict[str, Any] = {
        "dataset_id": args.dataset_id,
        "config_name": args.config_name,
        "repo_subdir": repo_subdir,
        "dataset_sha": dataset_info.sha,
        "splits": {},
        "audio_column": audio_column,
        "text_column": text_column,
    }

    for split in splits:
        split_dataset = dataset[split].cast_column(audio_column, Audio(decode=False))
        if args.max_rows_per_split:
            split_dataset = split_dataset.select(
                range(min(args.max_rows_per_split, len(split_dataset)))
            )
        rows = [
            _normalize_row(
                row=row,
                index=index,
                split=split,
                audio_column=audio_column,
                text_column=text_column,
                output_dir=output_dir,
                export_dir=exported_audio_dir / split,
            )
            for index, row in enumerate(split_dataset, start=1)
        ]
        manifest_path = manifests_dir / f"{split}.manifest.jsonl"
        manifest_path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )
        summary["splits"][split] = {
            "row_count": len(rows),
            "manifest_path": os.path.relpath(manifest_path, output_dir),
        }

    (output_dir / "materialization_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
